"""The figurine-cipher decoder — SPEC §7.3, docs/quality/F5_REPORT_C2.md §6.

This module can only do harm in one direction.  Failing to decode a damaged
page leaves it exactly as damaged as it already was; decoding a page that was
never damaged **destroys correct notation**, and does it silently, because the
output still looks like notation.  So the tests are weighted accordingly: the
safety property gets a synthetic half and a corpus half, and both halves have
a sabotage.

Every false positive pinned below was a real one found while building this, on
real books, and each cost a different guard:

=====================================  =========================================
what broke                             the guard
=====================================  =========================================
Russian ``Кс4`` read as a cipher       piece letters come from every locale
Russian ``Kd2`` — a *Latin* K          homoglyph folding
``Кра8—b7`` with an em-dash            the Unicode dash list
a Portuguese book printing ``Qf6``     the language of the prose is not the
                                       language of the moves
=====================================  =========================================
"""

from __future__ import annotations

import pytest

from caissa.ocr.notation import (
    CIPHER_SLOT,
    CipherReport,
    candidate_locales,
    decode,
    infer_cipher,
)

# --------------------------------------------------------------------------- #
# Correct notation, in every language the project claims
# --------------------------------------------------------------------------- #

#: Real notation, one line per locale.  Not one of these may be called a cipher.
CLEAN_PAGES = {
    "inglês": "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 "
              "7.Bb3 d6 8.c3 O-O 9.h3 Nb8 10.d4 Nbd7 11.Nbd2 Bb7 12.Bc2 Re8",
    "alemão": "1.e4 e5 2.Sf3 Sc6 3.Lb5 a6 4.La4 Sf6 5.O-O Le7 6.Te1 b5 "
              "7.Lb3 d6 8.c3 O-O 9.h3 Sb8 10.d4 Sbd7 11.Sbd2 Lb7 12.Lc2 Te8",
    "português": "1.e4 e5 2.Cf3 Cc6 3.Bb5 a6 4.Ba4 Cf6 5.O-O Be7 6.Te1 b5 "
                 "7.Bb3 d6 8.c3 O-O 9.h3 Cb8 10.d4 Cbd7 11.Cbd2 Bb7 12.Bc2 Te8",
    "russo": "1.e4 e5 2.Кf3 Кc6 3.Сb5 a6 4.Сa4 Кf6 5.O-O Сe7 6.Лe1 b5 "
             "7.Сb3 d6 8.c3 O-O 9.h3 Кb8 10.d4 Кbd7 11.Кbd2 Сb7 12.Сc2 Лe8",
    "figurino Unicode": "1.e4 e5 2.♘f3 ♘c6 3.♗b5 a6 4.♗a4 ♘f6 5.O-O ♗e7 "
                        "6.♖e1 b5 7.♗b3 d6 8.c3 O-O 9.h3 ♘b8 10.d4 ♘bd7 "
                        "11.♘bd2 ♗b7 12.♗c2 ♖e8",
}

#: Tesseract's real output for Gaprindashvili p202, copied verbatim.  The truth,
#: read off the rendered page: ``2...R8c7 3 Qd6+ Kg8 4 Qd8+`` and so on.
DAMAGED_PAGE = (
    "2...88c7 3 Wd6+ Sg8 4 Wd8+. 3 Wh2! 4 Hh7! 1-0 Since he loses a "
    "rook: 4...We5 5 Wxe5! Hxe5 6 Hh8+. 6 f7 h1=W 7 Axh1 a2 8 f8=W "
    "a1=W 9 Wf4+ Sh3 10 Wh4 mate"
)


@pytest.mark.parametrize("language,text", sorted(CLEAN_PAGES.items()))
def test_correct_notation_is_never_called_a_cipher(language, text):
    report = infer_cipher(text)
    assert not report.is_ciphered, (
        f"{language}: notação correta acusada de cifra — "
        f"{report.describe_pt()}")


@pytest.mark.parametrize("language,text", sorted(CLEAN_PAGES.items()))
def test_correct_notation_comes_back_byte_for_byte(language, text):
    """**The safety property.**  Not "mostly unchanged": identical."""
    assert decode(text, infer_cipher(text)) == text, language


def test_the_language_of_the_prose_is_not_the_language_of_the_moves():
    """A real false positive, pinned as the hazard it is.

    `400 Quebra-cabeças` p160 is a **Portuguese** book that prints its moves in
    **English**: ``17...Qf6!``, ``18...Nxg3``.  Told the page was Portuguese —
    which it is — the decoder treated ``Q`` and ``N`` as figurine stand-ins and
    rewrote eight correct moves into ``?f6``, ``?xg3``, ``?d2``.

    The default protects against this by accepting every locale's letters.  The
    narrow path still exists, and this test is what stands between the next
    caller and that trap.
    """
    page = ("Neste momento, o peão em g6 está protegendo o rei preto. "
            "17...Qf6! 18.Qd2 Nxg3 19.Qg4 Nxe4 20.Qg4 Qf6 21.Nxg3 Qd2 "
            "22.Qe3 Nf5 23.Qd4 Nxd4 24.Nf3 Qc5 25.Ne5 Qb4 26.Nd7 Qa3")

    assert not infer_cipher(page).is_ciphered
    assert decode(page, infer_cipher(page)) == page

    narrowed = infer_cipher(page, notation_lang="por")
    assert narrowed.is_ciphered, (
        "a armadilha desapareceu — se `por` já não acusa esta página, o "
        "aviso em _piece_letters está desatualizado")


#: Twenty correct English moves with two OCR smudges among them.  This is the
#: realistic dangerous page: mostly right, so a decoder that fires on any
#: symbol it sees would rewrite the twenty to fix the two.
MOSTLY_CLEAN_PAGE = (
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.Re1 b5 6.Bb3 d6 7.c3 Nb8 "
    "8.d4 Nbd7 9.Bc2 Re8 10.Nf1 Bf8 11.Ng3 g6 12.Bg5 h6 13.Be3 Nc5 "
    "14.Qd2 h5 15.Qxc4 Rb8 16.Rd1 Qc7 17.Nf5 Bg7 18.Wd6 Ne6 19.Wd5 Kh7"
)


def test_a_mostly_correct_page_is_not_rewritten_to_fix_two_tokens():
    """**The guard that keeps the decoder from being a net loss.**

    Two smudges among twenty correct moves.  ``W`` clears the support floor —
    it appears twice, which is the definition of a pattern — so the alphabet is
    not empty and every early return is bypassed.  What stops the rewrite is
    :attr:`CipherReport.is_ciphered`: the damage has to be the *majority* of
    the piece moves before anything is touched.

    Without it the decoder trades twenty right answers for two, which is the
    shape of every net-negative "fix" this project has rejected.
    """
    report = infer_cipher(MOSTLY_CLEAN_PAGE)
    assert "W" in {s.symbol for s in report.symbols}, (
        "o símbolo sumiu do alfabeto; o teste deixou de exercitar a guarda")
    assert report.clean_moves > report.ciphered_moves
    assert not report.is_ciphered
    assert decode(MOSTLY_CLEAN_PAGE, report) == MOSTLY_CLEAN_PAGE


def test_narrowing_to_russian_still_reads_a_latin_k(pymupdf):
    """The homoglyph guard, exercised where it is load-bearing.

    Under the safe default ``K`` and ``C`` are clean anyway — they are the
    English king and the Portuguese bishop — so that path proves nothing about
    homoglyphs.  It is the **narrowed** path that needs the fold: told the page
    is Russian, ``K`` is not a Russian letter at all, and without folding it to
    ``К`` every one of these correct moves reads as a cipher symbol.
    """
    page = " ".join(f"{n}.Kd2 Cc5 Kf6 Cd4" for n in range(1, 7))
    report = infer_cipher(page, notation_lang="rus")
    assert not report.is_ciphered, report.describe_pt()
    assert decode(page, report) == page


def test_a_latin_k_in_a_russian_book_is_not_a_cipher_symbol():
    """Homoglyph, not cipher — and the distinction decides who fixes it.

    A Russian PDF routinely carries the Latin ``K`` where the page printed the
    Cyrillic ``К``.  ``Kd2`` then parses as English "king to d2" when the book
    said "knight to d2": wrong, and silent, because it parses.  Rewriting it to
    ``?d2`` would destroy the one clue that survived.
    """
    page = ("Если 16...f5, то 17.Kd2 Kf7 18.Cc5 Cd4 19.Kf6 Cc5 "
            "20.Kd2 Cd4 21.Kf7 Cc5 22.Kf6 Cd4")
    report = infer_cipher(page)
    assert not report.is_ciphered, report.describe_pt()
    assert decode(page, report) == page


def test_long_notation_with_an_em_dash_is_read_as_a_move():
    """``Кра8—b7`` is a move, not four characters of damage."""
    for dash in "-‐‒–—−":
        page = " ".join(f"{n}.Кра8{dash}b7 Лd8{dash}d5" for n in range(1, 9))
        assert not infer_cipher(page).is_ciphered, dash


# --------------------------------------------------------------------------- #
# Damaged notation
# --------------------------------------------------------------------------- #


def test_a_ciphered_page_is_recognised():
    report = infer_cipher(DAMAGED_PAGE)
    assert report.is_ciphered
    assert report.ciphered_moves > report.clean_moves


def test_promotion_pins_the_queen():
    """The one symbol hard evidence resolves without a position.

    ``f8=W`` is a pawn reaching the eighth rank and becoming something.  In
    published games that something is a queen; under-promotion is rare enough
    to be a named event.  The truth here, read off the page: ``f8=♕``.
    """
    report = infer_cipher(DAMAGED_PAGE)
    assert report.assignment == {"W": "Q"}
    queen = next(s for s in report.symbols if s.symbol == "W")
    assert "promoção" in queen.evidence_pt

    decoded = decode(DAMAGED_PAGE, report)
    assert "Qd6+" in decoded and "Qxe5" in decoded
    assert "f8=Q" in decoded and "a1=Q" in decoded


def test_what_is_not_proved_is_marked_and_not_guessed():
    """``H`` is the rook, and this module must not say so.

    Frequency would let it guess, and a guess that parses is exactly the
    failure this project keeps finding.  The hole is written instead, so the
    caller can see there is one.
    """
    report = infer_cipher(DAMAGED_PAGE)
    decoded = decode(DAMAGED_PAGE, report)
    assert f"{CIPHER_SLOT}h7" in decoded
    assert not any(s.resolved for s in report.unresolved)
    assert {s.symbol for s in report.unresolved} == {"H"}


def test_the_price_of_the_safe_default_is_named_here():
    """``S`` on this page is the **king**, and the decoder leaves it alone.

    Not an oversight: ``S`` is the German and Dutch knight, so under the safe
    default it counts as a piece letter someone really prints, and a page that
    uses it as a figurine stand-in keeps those moves unreadable.  ``A`` and
    ``B`` cost the same way.

    That is the trade the module is built around, and it is worth a number.
    Measured over 8 Gaprindashvili pages and 6 Nunn pages, what is left
    unreadable after decoding:

    ==============  =================  ================
    setting         Gaprindashvili     Nunn
    ==============  =================  ================
    before any      79.8 %             79.2 %
    safe default    **33.9 %**         **31.0 %**
    narrowed        4.9 %              9.0 %
    ==============  =================  ================

    The narrowed column is better and is also what rewrote eight correct moves
    on a Portuguese page.  If this ever needs to be reopened, reopen it with
    the legality replay deciding, not with a wider alphabet.
    """
    report = infer_cipher(DAMAGED_PAGE)
    assert "S" not in {s.symbol for s in report.symbols}
    assert "Sg8" in decode(DAMAGED_PAGE, report)


def test_decoding_leaves_what_it_does_not_recognise_alone():
    """``88c7`` is a rook move whose glyph came back as two digits.  There is
    no single symbol to invert, so it must survive untouched rather than be
    improvised into something."""
    decoded = decode(DAMAGED_PAGE, infer_cipher(DAMAGED_PAGE))
    assert "88c7" in decoded


def test_a_symbol_seen_once_is_not_an_alphabet():
    """``A`` appears once in the page above.  Twice is a pattern; once is a
    smudge, and admitting it would let one bad glyph rewrite a real move."""
    report = infer_cipher(DAMAGED_PAGE)
    assert "A" not in {s.symbol for s in report.symbols}
    assert "Axh1" in decode(DAMAGED_PAGE, report)


def test_a_handful_of_moves_is_not_enough_to_judge():
    """Same floor the rest of the front uses, for the same reason."""
    assert not infer_cipher("1 Wd6+ Sg8 2 Wd8+").is_ciphered


# --------------------------------------------------------------------------- #
# Handing the rest to the legality replay
# --------------------------------------------------------------------------- #


def test_candidate_locales_enumerates_the_unresolved_symbols():
    """The hypotheses a caller hands to legality_repair once a position exists.

    With the queen pinned by promotion, one unknown symbol over the four
    remaining pieces gives four candidate assignments — a candidate space a
    whole-game replay eliminates in a ply or two.
    """
    report = infer_cipher(DAMAGED_PAGE)
    candidates = list(candidate_locales(report))
    assert len(candidates) == 4
    assert all(c["W"] == "Q" for c in candidates)
    assert all(len(set(c.values())) == len(c) for c in candidates), (
        "duas peças diferentes receberam a mesma letra")
    assert {"W": "Q", "H": "R"} in candidates, (
        "a atribuição verdadeira desta página não está entre as candidatas")


def test_a_fully_resolved_report_yields_one_candidate():
    report = CipherReport(symbols=(), clean_moves=20, ciphered_moves=0)
    assert list(candidate_locales(report)) == [{}]


def test_an_override_fills_the_holes():
    """How a settled reading comes back: the caller re-decodes with what the
    replay decided, and the holes close."""
    report = infer_cipher(DAMAGED_PAGE)
    decoded = decode(DAMAGED_PAGE, report, assignment={"H": "R"})
    assert "Rh7" in decoded and "Rxe5" in decoded and "Qd6+" in decoded
    assert CIPHER_SLOT not in decoded


# --------------------------------------------------------------------------- #
# The corpus half of the safety property
# --------------------------------------------------------------------------- #

#: Books whose text layer reads its notation correctly, across three scripts
#: and three notation languages.  Eighteen pages that must survive untouched.
_CLEAN_CORPUS = [
    ("dvoretsky", (204, 300, 408, 500, 612)),
    ("boleslavsky", (30, 45, 60, 75, 90)),
    ("quebra_cabecas", (40, 80, 120, 160)),
    ("capablanca", (100, 200, 300, 400)),
]


@pytest.mark.golden
@pytest.mark.parametrize("key,pages", _CLEAN_CORPUS)
def test_real_books_with_correct_notation_survive_untouched(
        pymupdf, corpus_doc, key, pages):
    """The synthetic half proves the rule; this proves it on real pages.

    Every false positive listed in this module's docstring was found here and
    nowhere else — synthetic notation is too clean to contain a Latin ``K`` in
    a Russian book, or a Portuguese book that prints English moves.  Four
    books, three scripts, **18 pages, byte for byte**.
    """
    doc = corpus_doc(key)
    checked = 0
    for index in pages:
        if index >= doc.page_count:
            continue
        text = doc[index].get_text("text") or ""
        if not text.strip():
            continue
        checked += 1
        report = infer_cipher(text)
        assert decode(text, report) == text, (
            f"{key} p{index}: o decodificador reescreveu notação correta — "
            f"{report.describe_pt()}")
    assert checked >= 4, f"{key}: só {checked} páginas tinham texto"


@pytest.mark.golden
def test_the_decoder_earns_its_place_on_a_damaged_corpus_page(
        pymupdf, corpus_doc):
    """The other half of a vitality proof: it must actually *do* something.

    A decoder that never fires is as useless as one that fires on everything,
    and every test above is about not firing.  This one runs the real Tesseract
    on Gaprindashvili p202 and requires the cipher to be found and the queen to
    be resolved by promotion.
    """
    import numpy as np

    from caissa.ocr.engines.tesseract import TesseractEngine
    from caissa.ocr.types import RegionKind

    engine = TesseractEngine()
    if not engine.available():
        pytest.skip(engine.unavailable_reason() or "Tesseract indisponível")

    doc = corpus_doc("gaprindashvili_ocr")
    pix = doc[202].get_pixmap(dpi=300, colorspace="gray")
    raster = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width)
    text = engine.recognize(raster, lang="eng",
                            psm_hint=RegionKind.PAGE).text

    report = infer_cipher(text)
    assert report.is_ciphered, report.describe_pt()
    assert report.assignment.get("W") == "Q", report.describe_pt()

    decoded = decode(text, report)
    assert decoded != text
    assert "Qd6+" in decoded, decoded[:200]
