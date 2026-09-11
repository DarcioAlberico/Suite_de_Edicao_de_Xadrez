"""Level 0 of the cascade: the PDF's own text layer, when it can be trusted.

A born-digital PDF already contains the exact characters the typesetter set.
Reading them beats OCR on every axis — it is instant, it is exact, and it keeps
the original spacing and font runs.  Level 0 exists so that the product never
OCRs a page it did not need to OCR.

The catch, and the reason this module is long, is that a PDF text layer can be
**confidently wrong**.  A subset-embedded font addresses its glyphs by index
and carries a ``ToUnicode`` CMap saying what each index means.  When that CMap
is missing, truncated, or maps everything to U+0000, the extractor still
returns a string — it just returns the wrong one.  The page looks perfect on
screen (the glyphs are drawn from outlines, not from Unicode) and copies out as
garbage.  This is common in chess PDFs, where figurine and diagram fonts are
routinely subset by tools that do not bother writing a CMap.

Silently emitting that garbage is the worst possible outcome: it is not flagged
low-confidence, it does not look like an OCR error, and it poisons the IR and
every export made from it.  So this module measures the layer before believing
it, along four independent axes:

1.  **Font structure** — is there a ``ToUnicode`` at all, and if so does it map
    to anything real?  A Type0/Identity-H subset with no CMap is broken beyond
    argument; a simple font with a standard encoding and no CMap is fine, and
    conflating the two rejects perfectly good pages.
2.  **Unmapped glyph ratio** — U+0000, U+FFFD, private-use and unassigned code
    points in the extracted string.
3.  **Dictionary hit rate** — a broken CMap is a substitution cipher, and a
    cipher preserves letter statistics but destroys words.
4.  **Character n-gram plausibility** — catches the cases with too little text
    for the dictionary to speak.

Any one of them can reject the layer, and the reason is always recorded so the
UI can tell the user *why* a page fell through to OCR.

``parse_tounicode`` and the font-dictionary walk are ported from
``PDFimport/PDFImport_v1.2.0/PDFImport/fontembed.py`` (``parse_tounicode``,
``_unicode_map_from_pdf``), absorbed 2026-09-07.  Changes: the original rebuilds
a usable ``cmap`` for font re-embedding and raises ``SkipFont`` on anything it
cannot handle; here the same parse is used only to *judge* the CMap, so the
error paths return a diagnosis instead of an exception, and the CIDToGIDMap
walk is dropped because glyph indices are irrelevant to the question asked.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from caissa.vision.detect.font_catalog import lookup_family

from ..lexicon import (
    dictionary_hit_rate,
    implausible_char_ratio,
    mangled_move_ratio,
    modelled_script_share,
    ngram_plausibility,
    nonword_ratio,
    normalise_lang,
)
from ..types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind, empty_result
from .base import EngineCapabilities, EngineLevel, OcrEngineBase

__all__ = [
    "PdfTextLayerEngine",
    "TextLayerVerdict",
    "TextLayerThresholds",
    "FontRisk",
    "FontRecord",
    "parse_tounicode",
    "inspect_fonts",
    "iter_page_verdicts",
]


# --------------------------------------------------------------------------- #
# ToUnicode parsing  (ported from PDFimport/fontembed.py)
# --------------------------------------------------------------------------- #

_HEX = re.compile(r"<([0-9A-Fa-f]+)>")


def _utf16(hexstr: str) -> str:
    hexstr = hexstr.strip()
    if len(hexstr) % 4:
        hexstr = hexstr.zfill(len(hexstr) + (4 - len(hexstr) % 4))
    try:
        return bytes.fromhex(hexstr).decode("utf-16-be", "replace")
    except ValueError:
        return ""


def parse_tounicode(data: bytes) -> dict[int, str]:
    """Character code -> text, from a ``ToUnicode`` CMap stream.

    Handles both ``bfchar`` (explicit pairs) and ``bfrange`` (a span mapped
    either to a consecutive run or to an explicit array).  The ``hi`` clamp
    guards against a malformed range asking for four billion entries, which is
    a real thing that malformed PDFs do.
    """
    text = data.decode("latin-1", "replace")
    out: dict[int, str] = {}
    for m in re.finditer(r"beginbfchar(.*?)endbfchar", text, re.S):
        toks = _HEX.findall(m.group(1))
        for i in range(0, len(toks) - 1, 2):
            out[int(toks[i], 16)] = _utf16(toks[i + 1])
    for m in re.finditer(r"beginbfrange(.*?)endbfrange", text, re.S):
        pattern = r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]+>)"
        for e in re.finditer(pattern, m.group(1)):
            lo, hi = int(e.group(1), 16), int(e.group(2), 16)
            hi = min(hi, lo + 0xFFFF)
            dst = e.group(3)
            if dst.startswith("["):
                for k, item in enumerate(_HEX.findall(dst)):
                    if lo + k <= hi:
                        out[lo + k] = _utf16(item)
                continue
            base = _utf16(dst[1:-1])
            if not base:
                continue
            for code in range(lo, hi + 1):
                last = ord(base[-1]) + (code - lo)
                if last > 0x10FFFF:
                    break
                out[code] = base[:-1] + chr(last)
    return out


# --------------------------------------------------------------------------- #
# Font inspection
# --------------------------------------------------------------------------- #


class FontRisk(StrEnum):
    """How much a font's structure threatens the extracted text."""

    #: Has a usable ToUnicode, or is a simple font with a standard encoding.
    OK = "ok"
    #: Structurally able to produce wrong text, but not proven to.
    SUSPECT = "suspect"
    #: Cannot possibly produce correct text.
    BROKEN = "broken"


#: Encodings for which a simple font needs no ToUnicode: the viewer, and
#: MuPDF, can map codes to Unicode from the encoding alone.
_STANDARD_ENCODINGS = frozenset({
    "WinAnsiEncoding", "MacRomanEncoding", "MacExpertEncoding",
    "StandardEncoding", "PDFDocEncoding",
})


@dataclass(slots=True)
class FontRecord:
    """What is known about one font resource on a page."""

    xref: int
    basefont: str
    resource_name: str
    subtype: str
    encoding: str
    has_tounicode: bool
    tounicode_entries: int
    #: Fraction of ToUnicode entries that map to nothing usable.
    dead_entry_ratio: float
    risk: FontRisk
    note: str = ""
    #: Characters drawn with this font on the page under inspection.
    char_count: int = 0

    @property
    def stem(self) -> str:
        """Base font name without the six-letter subset prefix."""
        return self.basefont.split("+", 1)[-1]


def _dead_entry_ratio(mapping: Mapping[int, str]) -> float:
    """Fraction of CMap entries that decode to nothing a reader could use."""
    if not mapping:
        return 1.0
    dead = 0
    for text in mapping.values():
        if not text:
            dead += 1
            continue
        # U+0000 is the canonical "the tool had nothing to write here"; the
        # replacement character and the private use area are the same failure
        # wearing a different hat.
        if all(ord(c) == 0 or ord(c) == 0xFFFD or 0xE000 <= ord(c) <= 0xF8FF
               or ord(c) < 0x20 for c in text):
            dead += 1
    return dead / len(mapping)


def _ref_number(value: str) -> int | None:
    match = re.match(r"\s*(\d+)\s+\d+\s+R", value or "")
    return int(match.group(1)) if match else None


def _read_tounicode(doc: Any, xref: int) -> bytes | None:
    """Fetch the ``ToUnicode`` stream of font ``xref``, following Type0 fonts
    down to their descendant when the parent has none."""
    try:
        kind, value = doc.xref_get_key(xref, "ToUnicode")
    except Exception:
        return None
    if kind == "xref":
        ref = _ref_number(value)
        if ref is not None:
            try:
                return doc.xref_stream(ref)
            except Exception:
                return None
    return None


def inspect_fonts(doc: Any, page: Any) -> list[FontRecord]:
    """Structural verdict on every font the page draws with.

    ``page.get_fonts(full=True)`` yields
    ``(xref, ext, type, basefont, resource_name, encoding, referencer)``.
    """
    records: list[FontRecord] = []
    try:
        entries = page.get_fonts(full=True)
    except Exception:
        return records

    for entry in entries:
        entry = list(entry) + [""] * (7 - len(entry))
        xref = int(entry[0]) if str(entry[0]).isdigit() else 0
        subtype = str(entry[2] or "")
        basefont = str(entry[3] or "")
        resource_name = str(entry[4] or "")
        encoding = str(entry[5] or "")

        raw = _read_tounicode(doc, xref) if xref else None
        mapping = parse_tounicode(raw) if raw else {}
        has_tounicode = bool(raw)
        dead_ratio = _dead_entry_ratio(mapping) if has_tounicode else 1.0

        risk, note = _classify_font(subtype, encoding, has_tounicode,
                                    len(mapping), dead_ratio)
        records.append(FontRecord(
            xref=xref,
            basefont=basefont,
            resource_name=resource_name,
            subtype=subtype,
            encoding=encoding,
            has_tounicode=has_tounicode,
            tounicode_entries=len(mapping),
            dead_entry_ratio=dead_ratio,
            risk=risk,
            note=note,
        ))
    return records


def _classify_font(subtype: str, encoding: str, has_tounicode: bool,
                   entries: int, dead_ratio: float) -> tuple[FontRisk, str]:
    """Decide a font's risk.

    The distinction that matters: a Type0 font with ``Identity-H`` addresses
    glyphs by index and carries no other route to Unicode, so a missing CMap is
    fatal.  A simple font with ``WinAnsiEncoding`` maps codes to Unicode
    through the encoding itself, so a missing CMap is normal and harmless.
    Treating both as "broken" rejects a large share of perfectly good PDFs.
    """
    is_type0 = subtype.lower().startswith("type0")
    identity = encoding.lower().startswith("identity")

    if has_tounicode and entries > 0:
        if dead_ratio >= 0.90:
            return (FontRisk.BROKEN,
                    "ToUnicode presente mas mapeia tudo para caracteres nulos.")
        if dead_ratio >= 0.30:
            return (FontRisk.SUSPECT,
                    f"ToUnicode com {dead_ratio:.0%} de entradas inúteis.")
        return FontRisk.OK, ""

    if has_tounicode and entries == 0:
        return (FontRisk.BROKEN,
                "ToUnicode presente mas vazio ou ilegível.")

    if is_type0 or identity:
        return (FontRisk.BROKEN,
                "fonte Type0/Identity sem ToUnicode: os códigos são índices de "
                "glifo e não têm significado textual.")

    if encoding in _STANDARD_ENCODINGS:
        return FontRisk.OK, ""

    if not encoding:
        return (FontRisk.SUSPECT,
                "fonte simples sem ToUnicode e sem codificação declarada.")

    return (FontRisk.SUSPECT,
            f"codificação não padronizada '{encoding}' sem ToUnicode.")


# --------------------------------------------------------------------------- #
# Verdict
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TextLayerThresholds:
    """Every number the verdict depends on, in one place so a build can tune
    them and a test can pin them."""

    #: Below this many non-space characters the page is treated as unscanned
    #: image, not as a bad text layer.
    min_chars: int = 24
    #: Dictionary and non-word rates are meaningless on a handful of tokens.
    min_judged_tokens: int = 12
    max_implausible_char_ratio: float = 0.15
    max_broken_font_char_ratio: float = 0.50
    min_dictionary_hit_rate: float = 0.12
    min_ngram_plausibility: float = 0.55
    max_nonword_ratio: float = 0.45
    #: A move-integrity ratio means nothing on a page that quotes two moves.
    #: Twelve is the same floor the lexical tests use, for the same reason.
    min_moves_for_notation_check: int = 12
    #: Above this share of damaged moves the page is marked as carrying
    #: unreliable notation.  Measured over 257 corpus pages: the two clean
    #: controls (Dvoretsky E1, Boleslavsky E6) peak at 0.062 and the three
    #: damaged books never fall below 0.187, so 0.15 sits in the gap with
    #: margin on both sides.  See docs/quality/F5_REPORT_C2.md §2.
    max_mangled_move_ratio: float = 0.15
    #: Above *this* share there is no usable notation left to salvage, and the
    #: layer is rejected outright rather than merely flagged.
    reject_mangled_move_ratio: float = 0.60
    #: Below this share of Latin letters the lexicon and the n-gram model have
    #: nothing to say and must abstain rather than vote "garbage".  0.50 rather
    #: than something higher because a Russian chess page is legitimately
    #: 10-15 % Latin (square names, ``1-0``, Western player names) and must
    #: still be treated as Cyrillic.
    min_modelled_script_share: float = 0.50
    #: Confidence assigned to words of an accepted layer.  Not 1.0: an accepted
    #: layer is very likely right, but "very likely" is not "certainly", and a
    #: hard 1.0 would make the arbiter unable to prefer anything over it.
    accepted_confidence: float = 0.98
    borderline_confidence: float = 0.80
    #: A page accepted on font structure alone, because no lexical test could
    #: read its script.  Below ``borderline`` on purpose: the arbiter must be
    #: able to prefer a real OCR engine's opinion over an unread page.
    unjudged_script_confidence: float = 0.70
    #: A page whose prose is fine but whose move text is damaged.  Deliberately
    #: low enough that the arbiter's level-0 bar of 0.82 is missed and a real
    #: OCR engine gets to compete for the page — which is the whole point of
    #: having a cascade.  The layer is still *accepted*: the prose is correct
    #: and throwing it away to save the moves would be the worse trade.
    damaged_notation_confidence: float = 0.55


@dataclass(frozen=True, slots=True)
class TextLayerVerdict:
    """Why the text layer was accepted or rejected, with the numbers."""

    accepted: bool
    reason: str
    confidence: float
    signals: Mapping[str, float] = field(default_factory=dict)
    fonts: tuple[FontRecord, ...] = ()
    #: True when the page simply has no text — a scan, not a broken layer.
    is_image_only: bool = False

    @property
    def broken_fonts(self) -> tuple[FontRecord, ...]:
        return tuple(f for f in self.fonts if f.risk is FontRisk.BROKEN)

    @property
    def suspect_fonts(self) -> tuple[FontRecord, ...]:
        return tuple(f for f in self.fonts if f.risk is FontRisk.SUSPECT)

    def describe_pt(self) -> str:
        """One-paragraph explanation for the UI."""
        head = ("Camada de texto aceita" if self.accepted
                else "Camada de texto rejeitada")
        detail = f"{head}: {self.reason}"
        broken = self.broken_fonts
        if broken:
            names = ", ".join(sorted({f.stem or f"xref {f.xref}"
                                      for f in broken})[:4])
            detail += f" Fontes comprometidas: {names}."
        return detail


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #


class PdfTextLayerEngine(OcrEngineBase):
    """Level 0: read the PDF's own text, after proving it is worth reading.

    The :class:`~caissa.ocr.engines.base.OcrEngine` protocol takes a raster, and
    this engine cannot work from one — so :meth:`recognize` returns an empty
    result with an explanation and the arbiter escalates.  The real entry point
    is :meth:`recognize_page`, which the arbiter calls when the region carries a
    PDF page.
    """

    name = "pdf_text_layer"

    def __init__(self, thresholds: TextLayerThresholds | None = None) -> None:
        super().__init__()
        self.thresholds = thresholds or TextLayerThresholds()

    # -- availability ------------------------------------------------------ #

    def _probe(self) -> tuple[bool, str | None]:
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            try:
                import fitz  # noqa: F401
            except ImportError:
                return False, (
                    "PyMuPDF não está instalado, portanto a camada de texto "
                    "dos PDFs não pode ser lida. Instale-o com "
                    "'pip install pymupdf'."
                )
        return True, None

    def _discover_languages(self) -> set[str]:
        # A text layer is already Unicode; language is a property of the book,
        # not of the extractor, so every language is served equally.
        return {"por", "eng", "deu", "rus", "spa", "fra", "ita", "nld", "any"}

    def supports_language(self, lang: str) -> bool:
        return self.available()

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.PDF_TEXT_LAYER,
            cost_per_megapixel_s=0.002,
            supports_char_boxes=True,
            supports_confidence=False,
            handles_layout=True,
            requires_pdf_page=True,
            gpu_capable=False,
        )

    # -- protocol conformance ---------------------------------------------- #

    def _recognize(self, image: NDArray[np.uint8], *, lang: str,
                   psm_hint: RegionKind) -> OcrResult:
        return empty_result(
            self.name, lang,
            region_kind=psm_hint,
            warning=("A camada de texto do PDF exige a página do documento, "
                     "não uma imagem rasterizada; o nível 0 foi ignorado."),
        )

    # -- assessment -------------------------------------------------------- #

    def assess(self, page: Any, *, lang: str = "",
               clip: BBox | None = None,
               ignore_diagram_fonts: bool = True) -> TextLayerVerdict:
        """Decide whether ``page``'s text layer can be trusted.

        Deterministic: the checks run in a fixed order and the first failure
        wins, so the same page always produces the same reason.

        ``ignore_diagram_fonts`` leaves the glyphs of a *diagram* font (the
        F3-A catalogue: Chess Merida, SkakNew-Diagram, ...) out of the text
        being judged.  They are a chess position, not language, and on a
        problem book they are most of the page: the Polgar's pages are 48
        board glyphs plus a number and a running head, and judged whole they
        score 8 % dictionary hits and are rejected -- every one of 11 sampled,
        for a layer that is perfectly good.  Found by the F2 importer,
        2026-09-11.  Inline figurine fonts are *not* excluded: their letters
        are the notation whose integrity ``mangled_move_ratio`` measures.
        """
        th = self.thresholds
        doc = page.parent
        fonts = inspect_fonts(doc, page)
        text = self._page_text(page, clip, ignore_diagram_fonts=ignore_diagram_fonts)
        char_total = sum(1 for c in text if not c.isspace())

        unattributed = self._attribute_chars(page, fonts, clip,
                                             ignore_diagram_fonts=ignore_diagram_fonts)
        broken_chars = sum(f.char_count for f in fonts
                           if f.risk is FontRisk.BROKEN)
        suspect_chars = sum(f.char_count for f in fonts
                            if f.risk is FontRisk.SUSPECT)
        attributed = sum(f.char_count for f in fonts)
        # Unattributed characters count against the denominator rather than
        # being ignored: a page where naming failed must not report "0 % broken"
        # with more authority than it has earned.
        denominator = attributed + unattributed or 1
        broken_ratio = broken_chars / denominator
        suspect_ratio = suspect_chars / denominator

        implausible, _ = implausible_char_ratio(text)
        langs = normalise_lang(lang)
        dict_rate, judged = dictionary_hit_rate(text, langs)
        nonword, nonword_n = nonword_ratio(text, langs)
        plausibility, _ = ngram_plausibility(text)
        # The n-gram model only speaks Latin, and the lexicon's non-Latin
        # coverage is the embedded core alone.  On a Cyrillic or Greek page
        # both terms report "garbage" for text that is perfectly correct, so
        # both abstain and the structural checks decide instead.  Measured on
        # E6 (Boleslavsky): five pages 88-93 % Cyrillic scored 0.000-0.115 for
        # n-gram plausibility, and page 60 — a correct table of Russian
        # figurine moves — was rejected outright before this guard.
        latin_share = modelled_script_share(text)
        lexical_terms_apply = latin_share >= th.min_modelled_script_share
        # Notation integrity is judged in *every* script.  A figurine font
        # breaks the same way on a Russian page as on an English one, and the
        # square names it leaves behind are Latin either way, so this is the
        # one lexical signal that must not abstain above.
        mangled_moves, moves_judged = mangled_move_ratio(text, langs)
        notation_judged = moves_judged >= th.min_moves_for_notation_check

        signals: dict[str, float] = {
            "char_total": float(char_total),
            "implausible_char_ratio": implausible,
            "broken_font_char_ratio": broken_ratio,
            "suspect_font_char_ratio": suspect_ratio,
            "dictionary_hit_rate": dict_rate,
            "judged_tokens": float(judged),
            "nonword_ratio": nonword,
            "nonword_tokens": float(nonword_n),
            "ngram_plausibility": plausibility,
            "mangled_move_ratio": mangled_moves,
            "moves_judged": float(moves_judged),
            "modelled_script_share": latin_share,
            "lexical_terms_apply": float(lexical_terms_apply),
            "font_count": float(len(fonts)),
            "unattributed_chars": float(unattributed),
        }

        def reject(reason: str, *, image_only: bool = False) -> TextLayerVerdict:
            return TextLayerVerdict(False, reason, 0.0, signals,
                                    tuple(fonts), image_only)

        if char_total < th.min_chars:
            return reject(
                f"a página contém apenas {char_total} caractere(s) de texto; "
                f"trata-se de uma digitalização, e o OCR será usado.",
                image_only=True,
            )

        if implausible > th.max_implausible_char_ratio:
            return reject(
                f"{implausible:.0%} dos caracteres extraídos são glifos não "
                f"mapeados (nulos, de uso privado ou fora de qualquer alfabeto "
                f"plausível), acima do limite de "
                f"{th.max_implausible_char_ratio:.0%}."
            )

        if broken_ratio > th.max_broken_font_char_ratio:
            return reject(
                f"{broken_ratio:.0%} do texto vem de fontes cujo ToUnicode está "
                f"ausente ou inutilizável, acima do limite de "
                f"{th.max_broken_font_char_ratio:.0%}."
            )

        if notation_judged and mangled_moves > th.reject_mangled_move_ratio:
            return reject(
                f"{mangled_moves:.0%} dos {moves_judged} lances da página "
                f"perderam o glifo da peça (a fonte de figurinos não "
                f"sobreviveu à extração): não resta notação aproveitável, "
                f"acima do limite de {th.reject_mangled_move_ratio:.0%}."
            )

        if judged >= th.min_judged_tokens and lexical_terms_apply:
            if (dict_rate < th.min_dictionary_hit_rate
                    and plausibility < th.min_ngram_plausibility):
                return reject(
                    f"apenas {dict_rate:.0%} das palavras extraídas existem em "
                    f"algum dos idiomas suportados e a plausibilidade de "
                    f"n-gramas é {plausibility:.2f}: o texto tem a forma de "
                    f"linguagem mas não é linguagem, sintoma clássico de CMap "
                    f"quebrado."
                )
            if nonword > th.max_nonword_ratio and nonword_n >= th.min_judged_tokens:
                return reject(
                    f"{nonword:.0%} das palavras extraídas são impronunciáveis "
                    f"em qualquer idioma suportado."
                )

        borderline = (
            suspect_ratio > 0.30
            or (lexical_terms_apply and judged >= th.min_judged_tokens
                and dict_rate < 2.0 * th.min_dictionary_hit_rate)
            or (lexical_terms_apply and plausibility < th.min_ngram_plausibility)
        )
        # Damaged notation outranks every verdict below, in any script.  It is
        # the failure a page-level lexical test is blind to by construction:
        # the prose is the bulk of the tokens and it is correct, so dictionary
        # rate, n-grams and non-word ratio all report a healthy page while the
        # move text — the reason the book exists — is gone.
        if notation_judged and mangled_moves > th.max_mangled_move_ratio:
            return TextLayerVerdict(
                True,
                f"a prosa está legível, mas {mangled_moves:.0%} dos "
                f"{moves_judged} lances desta página perderam o glifo da peça "
                f"— os figurinos voltaram como letras latinas quaisquer, no "
                f"padrão 'i'd6+ / l:th7. A camada foi aceita porque o texto "
                f"corrido é aproveitável; a notação desta página precisa de "
                f"revisão ou de OCR.",
                th.damaged_notation_confidence, signals, tuple(fonts), False)

        # A page the lexical tests could not judge is accepted on its structure
        # alone, and says so.  It is not "confidently fine": nothing here read
        # the words.
        if not lexical_terms_apply:
            return TextLayerVerdict(
                True,
                f"a página está escrita em um alfabeto que o léxico e o modelo "
                f"de n-gramas desta versão não cobrem "
                f"({1.0 - latin_share:.0%} de caracteres não latinos); os "
                f"glifos estão mapeados e a estrutura das fontes está correta, "
                f"portanto a camada foi aceita apenas por esses indícios.",
                th.unjudged_script_confidence, signals, tuple(fonts), False)

        confidence = (th.borderline_confidence if borderline
                      else th.accepted_confidence)
        reason = (
            "os glifos estão mapeados e o texto corresponde a um idioma "
            "conhecido."
            if not borderline else
            "o texto é utilizável, mas alguns indicadores estão fracos; "
            "convém revisar a página."
        )
        return TextLayerVerdict(True, reason, confidence, signals,
                                tuple(fonts), False)

    # -- extraction -------------------------------------------------------- #

    @staticmethod
    def _clip_rect(page: Any, clip: BBox | None) -> Any:
        if clip is None:
            return None
        import pymupdf
        return pymupdf.Rect(clip.x0, clip.y0, clip.x1, clip.y1)

    def _page_text(self, page: Any, clip: BBox | None, *,
                   ignore_diagram_fonts: bool = False) -> str:
        if ignore_diagram_fonts:
            return self._prose_text(page, clip)
        try:
            rect = self._clip_rect(page, clip)
            return page.get_text("text", clip=rect) or ""
        except Exception:
            try:
                return page.get_text() or ""
            except Exception:
                return ""

    @staticmethod
    def _is_diagram_font(name: str) -> bool:
        family = lookup_family(name)
        return family is not None and family.kind == "diagram"

    def _prose_text(self, page: Any, clip: BBox | None) -> str:
        """The page's text with every diagram-font span left out.

        Built from ``dict`` so spans can be judged by font; the ``text`` mode
        has no font information.  Lines are joined the way ``text`` mode
        joins them, so the lexical signals see the same word boundaries.
        """
        try:
            rect = self._clip_rect(page, clip)
            data = page.get_text("dict", clip=rect)
        except Exception:
            return self._page_text(page, clip)
        lines: list[str] = []
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                kept = [
                    str(span.get("text", "") or "")
                    for span in line.get("spans", [])
                    if not self._is_diagram_font(str(span.get("font", "")))
                ]
                joined = "".join(kept)
                if joined.strip():
                    lines.append(joined)
        return "\n".join(lines)

    def _attribute_chars(self, page: Any, fonts: Sequence[FontRecord],
                         clip: BBox | None, *,
                         ignore_diagram_fonts: bool = False) -> int:
        """Count how many characters each font actually draws; return the
        number that could not be attributed to any of them.

        Without this the font verdict is unweighted, and a single broken
        decorative font used for one drop cap would condemn a whole page whose
        body text is perfect.

        Matching is fuzzy on purpose.  ``page.get_fonts`` reports the font
        dictionary's ``BaseFont`` ("Times New Roman Regular") while
        ``get_text`` reports the name MuPDF derives for the span ("Times New
        Roman"); they routinely differ by a style suffix, by spaces, or by the
        six-letter subset prefix.  An exact comparison silently attributes
        nothing, which zeroes the broken-font ratio and disables the very
        check this function exists to feed.
        """
        for record in fonts:
            record.char_count = 0
        if not fonts:
            return 0

        index: dict[str, list[FontRecord]] = {}
        for record in fonts:
            for key in self._name_keys(record.basefont) | \
                    self._name_keys(record.resource_name):
                index.setdefault(key, []).append(record)

        try:
            rect = self._clip_rect(page, clip)
            data = page.get_text("dict", clip=rect)
        except Exception:
            return 0

        unattributed = 0
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    name = str(span.get("font", ""))
                    text = span.get("text", "") or ""
                    count = sum(1 for c in text if not c.isspace())
                    if not count:
                        continue
                    if ignore_diagram_fonts and self._is_diagram_font(name):
                        continue
                    targets = self._match_font(name, index, fonts)
                    if not targets:
                        unattributed += count
                        continue
                    # Split evenly when a name is ambiguous; ambiguity is rare
                    # and halving is better than picking arbitrarily.
                    share = count / len(targets)
                    for record in targets:
                        record.char_count += int(round(share))
        return unattributed

    @staticmethod
    def _name_keys(name: str) -> set[str]:
        """Progressively looser lookup keys for a font name."""
        if not name:
            return set()
        stem = name.split("+", 1)[-1].lower()
        squeezed = re.sub(r"[\s_-]+", "", stem)
        keys = {stem, squeezed}
        # Drop a trailing style word so "timesnewromanregular" also answers to
        # "timesnewroman", which is what get_text reports.
        for suffix in ("regular", "roman", "book", "medium", "normal"):
            if squeezed.endswith(suffix) and len(squeezed) > len(suffix) + 2:
                keys.add(squeezed[: -len(suffix)])
        return {k for k in keys if k}

    @classmethod
    def _match_font(cls, span_name: str,
                    index: Mapping[str, list[FontRecord]],
                    fonts: Sequence[FontRecord]) -> list[FontRecord]:
        for key in sorted(cls._name_keys(span_name), key=len, reverse=True):
            hit = index.get(key)
            if hit:
                return hit
        squeezed = re.sub(r"[\s_-]+", "",
                          span_name.split("+", 1)[-1].lower())
        if squeezed:
            partial = [f for f in fonts
                       if any(k.startswith(squeezed) or squeezed.startswith(k)
                              for k in cls._name_keys(f.basefont))]
            if partial:
                return partial
        # One font on the page and one unmatched span: it can only be that font.
        if len(fonts) == 1:
            return list(fonts)
        return []

    # -- recognition ------------------------------------------------------- #

    def recognize_page(
        self,
        page: Any,
        *,
        lang: str = "",
        clip: BBox | None = None,
        scale: float = 1.0,
        psm_hint: RegionKind = RegionKind.PAGE,
        verdict: TextLayerVerdict | None = None,
        force: bool = False,
    ) -> OcrResult:
        """Extract the text layer of ``page`` as a full :class:`OcrResult`.

        ``scale`` converts PDF points into the pixel space of the raster the
        other engines see (``dpi / 72``), so a caller can compare a level-0
        result with a level-1 result box for box.

        When the layer is rejected the result is empty and carries the reason,
        unless ``force`` is set — which exists for the UI's "show me what the
        PDF actually says" inspector, never for the pipeline.
        """
        started = time.perf_counter()
        if not self.available():
            return empty_result(self.name, lang, region_kind=psm_hint,
                                warning=self.unavailable_reason())

        if verdict is None:
            verdict = self.assess(page, lang=lang, clip=clip)

        meta: dict[str, object] = {
            "verdict": verdict.reason,
            "accepted": verdict.accepted,
            "is_image_only": verdict.is_image_only,
            "signals": dict(verdict.signals),
            "fonts": [
                {
                    "basefont": f.basefont,
                    "subtype": f.subtype,
                    "encoding": f.encoding,
                    "risk": str(f.risk),
                    "chars": f.char_count,
                    "note": f.note,
                }
                for f in verdict.fonts
            ],
            "scale": scale,
        }

        if not verdict.accepted and not force:
            return empty_result(
                self.name, lang,
                region_kind=psm_hint,
                duration_s=time.perf_counter() - started,
                warning=verdict.describe_pt(),
                **meta,
            )

        lines = self._extract_lines(page, clip=clip, scale=scale,
                                    confidence=verdict.confidence,
                                    region_kind=psm_hint)
        warnings: tuple[str, ...] = ()
        if force and not verdict.accepted:
            warnings = (
                "Extração forçada de uma camada de texto reprovada: "
                + verdict.describe_pt(),
            )
        return OcrResult(
            engine=self.name,
            lang=lang or "any",
            lines=tuple(lines),
            region_kind=psm_hint,
            duration_s=time.perf_counter() - started,
            warnings=warnings,
            meta=meta,
        )

    def _extract_lines(self, page: Any, *, clip: BBox | None, scale: float,
                       confidence: float,
                       region_kind: RegionKind) -> list[OcrLine]:
        """Build lines/words/chars from PyMuPDF's ``rawdict``.

        ``rawdict`` is the only extraction mode that reports a box per
        character, which is what makes level 0 interchangeable with an OCR
        engine downstream instead of a special case everything has to know
        about.
        """
        try:
            rect = self._clip_rect(page, clip)
            data = page.get_text("rawdict", clip=rect)
        except Exception:
            return []

        out: list[OcrLine] = []
        for block_index, block in enumerate(data.get("blocks", [])):
            if block.get("type") != 0:
                continue
            for line_index, line in enumerate(block.get("lines", [])):
                words = self._line_words(line, scale=scale,
                                         confidence=confidence,
                                         block_index=block_index,
                                         line_index=line_index)
                if not words:
                    continue
                lb = line.get("bbox") or (0, 0, 0, 0)
                box = BBox.from_edges(*lb).scaled(scale)
                baseline = self._baseline(line, box, scale)
                size = max((s.get("size", 0.0)
                            for s in line.get("spans", [])), default=0.0)
                out.append(OcrLine(
                    words=tuple(words),
                    box=box,
                    baseline=baseline,
                    block_index=block_index,
                    paragraph_index=block_index,
                    line_index=line_index,
                    kind=region_kind,
                    font_size=size * scale,
                ))
        return out

    @staticmethod
    def _baseline(line: Mapping[str, Any], box: BBox,
                  scale: float) -> tuple[float, float] | None:
        """Convert PDF span origins into the hOCR ``(slope, intercept)`` form.

        Using the same convention as Tesseract means downstream code has one
        baseline model rather than two.
        """
        spans = line.get("spans") or []
        origins = [s.get("origin") for s in spans if s.get("origin")]
        if not origins:
            return None
        y = origins[0][1] * scale
        direction = line.get("dir") or (1.0, 0.0)
        try:
            dx, dy = float(direction[0]), float(direction[1])
        except (TypeError, ValueError, IndexError):
            dx, dy = 1.0, 0.0
        slope = (dy / dx) if abs(dx) > 1e-9 else 0.0
        return slope, y - box.y1

    @staticmethod
    def _line_words(line: Mapping[str, Any], *, scale: float,
                    confidence: float, block_index: int,
                    line_index: int) -> list[OcrWord]:
        """Split a line's character stream into words at whitespace.

        PDF has no notion of a word: a space is just a glyph or a positioning
        operator.  Splitting on the extracted whitespace reproduces what the
        text stream actually claims, and leaves the harder question of implied
        spaces (kerned runs with no space glyph) to the layout stage, which has
        the font metrics to answer it.
        """
        words: list[OcrWord] = []
        pending: list[OcrChar] = []
        word_index = 0

        def flush() -> None:
            nonlocal pending, word_index
            if not pending:
                return
            text = "".join(c.text for c in pending)
            if text.strip():
                words.append(OcrWord(
                    text=text,
                    box=BBox.union_of([c.box for c in pending]),
                    confidence=confidence,
                    chars=tuple(pending),
                    block_index=block_index,
                    paragraph_index=block_index,
                    line_index=line_index,
                    word_index=word_index,
                ))
                word_index += 1
            pending = []

        for span in line.get("spans", []):
            for char in span.get("chars", []):
                ch = char.get("c", "")
                if not ch or ch.isspace():
                    flush()
                    continue
                cb = char.get("bbox") or (0, 0, 0, 0)
                pending.append(OcrChar(
                    text=ch,
                    box=BBox.from_edges(*cb).scaled(scale),
                    confidence=confidence,
                    inherited_confidence=True,
                ))
        flush()
        return words


def iter_page_verdicts(doc: Any, pages: Iterable[int], *, lang: str = "",
                       engine: PdfTextLayerEngine | None = None
                       ) -> list[tuple[int, TextLayerVerdict]]:
    """Assess a range of pages — the cheap pre-flight the batch importer runs
    to decide, before any rendering, which pages need OCR at all."""
    engine = engine or PdfTextLayerEngine()
    return [(pno, engine.assess(doc[pno], lang=lang)) for pno in pages]
