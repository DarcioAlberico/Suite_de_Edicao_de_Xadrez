"""Level 0 — the PDF's own text layer, and the four ways it lies.

Two halves.

The **synthetic** half builds PDFs here, breaks their ``ToUnicode`` in a named
way, and asserts the layer is rejected.  Ground truth is exact because the test
did the breaking.

The **corpus** half runs the same detector over real books from
``docs/quality/CORPUS.md`` and asserts the verdicts that were actually
measured.  These are pinned rather than merely printed, because the whole point
of level 0 is that its mistakes are silent: a page wrongly accepted produces
plausible-looking garbage that flows into the IR and out into every export, and
nothing downstream ever flags it.  A test that only checks "assess() returned a
verdict" would not have caught any of the three real defects these numbers pin.
"""

from __future__ import annotations

import pytest

from caissa.ocr.engines.pdf_text_layer import (
    FontRisk,
    PdfTextLayerEngine,
    TextLayerThresholds,
    inspect_fonts,
    parse_tounicode,
)
from caissa.ocr.lexicon import script_profile, modelled_script_share

from .conftest import (
    blank_pdf,
    break_tounicode,
    build_pdf,
    dead_tounicode_stream,
    requires_font,
    requires_pymupdf,
)

pytestmark = requires_pymupdf


# --------------------------------------------------------------------------- #
# ToUnicode parsing
# --------------------------------------------------------------------------- #


def test_parse_tounicode_reads_bfchar():
    cmap = (b"begincmap\n2 beginbfchar\n<0003> <0041>\n<0004> <0042>\n"
            b"endbfchar\nendcmap\n")
    assert parse_tounicode(cmap) == {3: "A", 4: "B"}


def test_parse_tounicode_reads_a_consecutive_bfrange():
    cmap = b"beginbfrange\n<0010> <0013> <0041>\nendbfrange\n"
    assert parse_tounicode(cmap) == {0x10: "A", 0x11: "B", 0x12: "C", 0x13: "D"}


def test_parse_tounicode_reads_an_array_bfrange():
    cmap = b"beginbfrange\n<0020> <0022> [<0058> <0059> <005A>]\nendbfrange\n"
    assert parse_tounicode(cmap) == {0x20: "X", 0x21: "Y", 0x22: "Z"}


def test_parse_tounicode_clamps_an_absurd_range():
    """A malformed range must not ask for four billion entries."""
    cmap = b"beginbfrange\n<0000> <FFFFFF> <0041>\nendbfrange\n"
    assert len(parse_tounicode(cmap)) <= 0x10000


def test_parse_tounicode_survives_garbage():
    assert parse_tounicode(b"not a cmap at all") == {}
    assert parse_tounicode(b"") == {}


def test_dead_cmap_parses_but_maps_to_nothing():
    """The generator produces a CMap that a naive check would pass."""
    mapping = parse_tounicode(dead_tounicode_stream(64))
    assert len(mapping) == 63, "a CMap morta precisa parecer preenchida"
    assert all(ord(v) == 0 for v in mapping.values())


# --------------------------------------------------------------------------- #
# Font structure
# --------------------------------------------------------------------------- #


@requires_font
def test_embedded_font_with_a_good_cmap_is_ok():
    doc = build_pdf()
    records = inspect_fonts(doc, doc[0])
    assert records, "o PDF de teste não declarou nenhuma fonte"
    assert all(r.risk is FontRisk.OK for r in records), [
        (r.basefont, str(r.risk), r.note) for r in records]
    doc.close()


@requires_font
def test_font_without_tounicode_is_broken():
    doc = break_tounicode(build_pdf(), mode="delete")
    records = inspect_fonts(doc, doc[0])
    broken = [r for r in records if r.risk is FontRisk.BROKEN]
    assert broken, [(r.basefont, str(r.risk), r.encoding, r.has_tounicode)
                    for r in records]
    assert "Identity" in broken[0].note or "Type0" in broken[0].note
    doc.close()


@requires_font
def test_font_with_a_dead_tounicode_is_broken():
    doc = break_tounicode(build_pdf(), mode="dead")
    records = inspect_fonts(doc, doc[0])
    broken = [r for r in records if r.risk is FontRisk.BROKEN]
    assert broken, [(r.basefont, str(r.risk), r.tounicode_entries,
                     r.dead_entry_ratio) for r in records]
    assert broken[0].dead_entry_ratio >= 0.90
    doc.close()


def test_a_base14_font_needs_no_cmap():
    """The distinction that stops the detector rejecting good PDFs.

    A simple font with a standard encoding maps codes to Unicode through the
    encoding itself.  Treating it like a Type0 subset would reject a large
    share of perfectly good documents.
    """
    doc = build_pdf(embed_font=False)
    records = inspect_fonts(doc, doc[0])
    assert records
    assert all(r.risk is FontRisk.OK for r in records), [
        (r.basefont, r.encoding, r.note) for r in records]
    doc.close()


def test_inspect_fonts_on_a_page_with_no_fonts():
    doc = blank_pdf()
    assert inspect_fonts(doc, doc[0]) == []
    doc.close()


# --------------------------------------------------------------------------- #
# The verdict, on PDFs this file broke
# --------------------------------------------------------------------------- #


@requires_font
def test_a_good_text_layer_is_accepted():
    doc = build_pdf()
    verdict = PdfTextLayerEngine().assess(doc[0], lang="eng")
    assert verdict.accepted, verdict.reason
    assert verdict.confidence >= 0.80
    assert not verdict.broken_fonts
    assert verdict.signals["dictionary_hit_rate"] > 0.40
    doc.close()


@requires_font
def test_a_deleted_cmap_is_rejected():
    """The failure this front exists to catch (SPEC §7.1 level 0)."""
    doc = break_tounicode(build_pdf(), mode="delete")
    verdict = PdfTextLayerEngine().assess(doc[0], lang="eng")
    assert not verdict.accepted, (
        f"uma camada com ToUnicode ausente foi ACEITA: {verdict.reason}\n"
        f"sinais: {dict(verdict.signals)}")
    assert verdict.confidence == 0.0
    assert not verdict.is_image_only, "não é uma digitalização, é camada quebrada"
    assert verdict.describe_pt()
    doc.close()


@requires_font
def test_a_dead_cmap_is_rejected():
    """Present-but-useless is the harder case: ``has ToUnicode`` is True."""
    doc = break_tounicode(build_pdf(), mode="dead")
    verdict = PdfTextLayerEngine().assess(doc[0], lang="eng")
    assert not verdict.accepted, (
        f"uma camada com ToUnicode morta foi ACEITA: {verdict.reason}\n"
        f"sinais: {dict(verdict.signals)}")
    assert verdict.confidence == 0.0
    doc.close()


@requires_font
def test_rejection_names_a_measured_reason():
    """Every rejection has to say *why*, with the number that decided it."""
    for mode in ("delete", "dead"):
        doc = break_tounicode(build_pdf(), mode=mode)
        verdict = PdfTextLayerEngine().assess(doc[0], lang="eng")
        assert verdict.reason, mode
        assert "%" in verdict.reason or "caractere" in verdict.reason, (
            f"motivo sem número, modo {mode}: {verdict.reason}")
        doc.close()


def test_a_page_with_no_text_is_image_only_not_broken():
    """A scan and a broken layer are different problems with different fixes.

    Reporting a scan as "broken text layer" would send the user looking for a
    PDF problem that does not exist.
    """
    doc = blank_pdf()
    verdict = PdfTextLayerEngine().assess(doc[0], lang="eng")
    assert not verdict.accepted
    assert verdict.is_image_only
    assert "digitaliza" in verdict.reason
    doc.close()


@requires_font
def test_the_verdict_is_deterministic():
    doc = break_tounicode(build_pdf(), mode="dead")
    engine = PdfTextLayerEngine()
    first = engine.assess(doc[0], lang="eng")
    second = engine.assess(doc[0], lang="eng")
    assert first.accepted == second.accepted
    assert first.reason == second.reason
    assert dict(first.signals) == dict(second.signals)
    doc.close()


@requires_font
def test_thresholds_are_injectable():
    """A build must be able to tune the detector without editing it."""
    doc = build_pdf()
    # Both bars set beyond 1.0, i.e. unreachable, so the assertion is about
    # the thresholds being honoured and not about where they happen to sit.
    strict = TextLayerThresholds(min_dictionary_hit_rate=1.01,
                                 min_ngram_plausibility=1.01)
    verdict = PdfTextLayerEngine(strict).assess(doc[0], lang="eng")
    assert not verdict.accepted
    doc.close()


@requires_font
def test_recognize_page_returns_word_boxes_for_an_accepted_layer():
    doc = build_pdf()
    result = PdfTextLayerEngine().recognize_page(doc[0], lang="eng")
    assert result.words, "a camada aceita não devolveu palavras"
    assert result.text.strip()
    assert all(w.box.w > 0 and w.box.h > 0 for w in result.words)
    # Not 1.0: an accepted layer is very likely right, and the arbiter must
    # still be able to prefer something over it.
    assert 0.0 < result.mean_confidence < 1.0
    doc.close()


@requires_font
def test_recognize_page_refuses_a_rejected_layer():
    doc = break_tounicode(build_pdf(), mode="dead")
    result = PdfTextLayerEngine().recognize_page(doc[0], lang="eng")
    assert result.is_empty or result.warnings, (
        "uma camada rejeitada devolveu texto sem aviso")
    doc.close()


def test_the_engine_refuses_a_raster():
    """Level 0 needs the document page; handed pixels it must say so."""
    import numpy as np
    engine = PdfTextLayerEngine()
    result = engine.recognize(np.full((80, 200), 255, dtype=np.uint8),
                              lang="eng")
    assert result.is_empty
    assert result.warnings and "rasteriz" in result.warnings[0]


# --------------------------------------------------------------------------- #
# The corpus (docs/quality/CORPUS.md)
# --------------------------------------------------------------------------- #

#: Pages sampled per book.  Fixed indices, not random: a flaky corpus test is
#: worse than none, and CORPUS.md §5 wants a number that can be re-measured.
_E8_GAPRINDASHVILI = (28, 72, 115, 158, 202, 245)
_E8_DOBONOV = (8, 20, 33, 45, 58, 70)
_E1_DVORETSKY = (204, 300, 408, 500, 612)
_E1_AAGAARD = (74, 100, 148, 222, 260)
_E2_NUNN = (120, 150, 200, 250)


def _verdicts(doc, pages, lang):
    engine = PdfTextLayerEngine()
    return {i: engine.assess(doc[i], lang=lang) for i in pages
            if i < doc.page_count}


@pytest.mark.golden
def test_e1_born_digital_layers_are_accepted(corpus_doc):
    """E1 is the control.  A detector that rejects these is useless.

    Measured 2026-09-07: Dvoretsky 5/5 and Aagaard 5/5 accepted, dictionary hit
    rate 0.80-0.97 with the trunk's word lists loaded.

    Both books are still accepted, and Dvoretsky is still accepted at full
    confidence.  What changed on 2026-09-10 is Aagaard, and it is a **second
    correction to CORPUS.md's E1**, of the same kind as Flores Rios below:

    *Practical Chess Defence* is not born-digital either.  Every font on its
    pages is a synthesised ``Fd######-Identity-H`` subset — the signature of a
    scan re-OCR'd by a commercial engine — and its figurines did not survive:
    ``♘xe5`` comes back as ``ll'lxe5`` and ``♕h5`` as ``ti'h5``.  Measured over
    45 pages, the median share of damaged moves is 0.271.  So three of the five
    sampled pages now come back at 0.55 with the notation flagged, and that is
    the *correct* reading of a page whose prose is perfect and whose moves are
    gone.  See docs/quality/F5_REPORT_C2.md §2.
    """
    doc = corpus_doc("dvoretsky")
    verdicts = _verdicts(doc, _E1_DVORETSKY, "eng")
    rejected = {i: v.reason for i, v in verdicts.items() if not v.accepted}
    assert not rejected, f"dvoretsky: páginas nativas rejeitadas: {rejected}"
    # Genuinely born-digital: full confidence, and no damaged notation at all.
    assert all(v.confidence >= 0.98 for v in verdicts.values())
    assert all(v.signals["mangled_move_ratio"] == 0.0
               for v in verdicts.values()), (
        "Dvoretsky é o controle limpo: um único lance acusado aqui é falso "
        "positivo do detector de notação, não defeito do livro.")

    doc = corpus_doc("aagaard")
    verdicts = _verdicts(doc, _E1_AAGAARD, "eng")
    rejected = {i: v.reason for i, v in verdicts.items() if not v.accepted}
    assert not rejected, f"aagaard: páginas nativas rejeitadas: {rejected}"
    damaged = {i for i, v in verdicts.items()
               if v.signals["mangled_move_ratio"] > 0.15}
    assert damaged == {148, 222, 260}, (
        f"a notação danificada do Aagaard mudou de página: {damaged}")
    for i, verdict in verdicts.items():
        expected = 0.55 if i in damaged else 0.98
        assert verdict.confidence == expected, (i, verdict.reason)


@pytest.mark.golden
def test_flores_rios_has_no_text_layer_at_all(corpus_doc):
    """CORPUS.md files this book under E1 "modern digital production".

    It is not born-digital in the sense level 0 cares about: it carries no text
    layer, so it is an image-only PDF and must be reported as a scan rather
    than as a broken layer.  Pinning this stops the next reader assuming E1
    implies "has a good text layer".
    """
    doc = corpus_doc("flores_rios")
    verdicts = _verdicts(doc, (116, 233, 349), "eng")
    assert verdicts
    for i, verdict in verdicts.items():
        assert not verdict.accepted, i
        assert verdict.is_image_only, (i, verdict.reason)
        assert verdict.signals["char_total"] == 0.0


@pytest.mark.golden
def test_gaprindashvili_third_party_ocr_layer(corpus_doc):
    """E8: a book that already went through somebody else's OCR.

    What the detector actually does, measured 2026-09-07:

    ===========  =========  =====================================
    page         verdict    why
    ===========  =========  =====================================
    28, 72, 115  image-only the reprocessing dropped the layer
    158          kept 0.55  48 % "unpronounceable" — mostly mangled moves (passo 6)
    202, 245     accepted   at 0.98
    ===========  =========  =====================================

    The first two rows are right.  The third was the honest weakness of a
    page-level verdict: the prose on 202 and 245 is fine, but their move text
    is destroyed — the Batsford figurines came back as ``'i'd6+``, ``l:th7``,
    ``J:!.'.8c7`` — and the prose outvoted it in every lexical signal.

    **That is now fixed.**  ``mangled_move_ratio`` (F5_REPORT_C2 §2) reads the
    damage directly instead of hoping a prose signal notices it:

    ===========  ===================  ===================  ==============
    page         damaged-move ratio   moves judged         confidence
    ===========  ===================  ===================  ==============
    202          0.157                83                   0.55
    245          0.231                121                  0.55
    ===========  ===================  ===================  ==============

    The bar is 0.15, and it was **not** chosen to catch these two pages: it
    comes from the distribution over the whole 50-book collection, where the
    clean controls peak at 0.065 and the damaged books never fall below 0.195.
    Tuning a bar to a named page is how a gate gets bought (F7 cycle 2).

    Note what per-region arbitration would *not* have fixed, since that was
    the plan of record in F5_REPORT §5: measured on this very page, the prose
    and the destroyed moves share the same lines — ``"For the present White
    cannot play 1 !txg7 Wxg7 2 .tel l:txcl+"`` — so no geometric cut separates
    them.  See F5_REPORT_C2 §1.
    """
    doc = corpus_doc("gaprindashvili_ocr")
    verdicts = _verdicts(doc, _E8_GAPRINDASHVILI, "eng")

    for page in (28, 72, 115):
        assert verdicts[page].is_image_only, (page, verdicts[page].reason)

    # Page 158 used to be *rejected* for 48 % unpronounceable words — 29 of
    # its 40 "words" were mangled moves (``Wh2t``).  Since OCR_UI_ROADMAP
    # passo 6 those count as notation, not words: the page is kept at 0,55
    # like the other two, with 37 % of 149 moves damaged, and the OCR
    # contests it (passo 2) instead of replacing the whole page.
    assert verdicts[158].accepted and verdicts[158].notation_damaged, verdicts[158].reason
    assert verdicts[158].confidence == 0.55
    assert verdicts[158].signals["nonword_ratio"] < 0.45
    assert verdicts[158].signals["mangled_move_ratio"] == pytest.approx(0.369, abs=0.005)

    # Both stay accepted: the prose is correct and worth keeping, and throwing
    # a good page away to save its moves is the worse trade.  What changed is
    # that both now say their notation is unreliable, at a confidence low
    # enough for the arbiter's level-0 bar of 0.82 to send the page on.
    for page, ratio, moves in ((202, 0.157, 83), (245, 0.231, 121)):
        verdict = verdicts[page]
        assert verdict.accepted, (page, verdict.reason)
        assert verdict.confidence == 0.55, (page, verdict.reason)
        assert verdict.signals["moves_judged"] == moves, page
        assert verdict.signals["mangled_move_ratio"] == pytest.approx(
            ratio, abs=0.001), (page, verdict.signals["mangled_move_ratio"])
        assert "glifo da peça" in verdict.reason, page


@pytest.mark.golden
def test_dobonov_third_party_ocr_layer_is_usable(corpus_doc):
    """E8, the other already-OCR'd book, and the opposite outcome.

    This one is in Spanish descriptive notation (``2. CxT``), which uses plain
    letters rather than a figurine font, so the third-party OCR had nothing to
    destroy and the layer is genuinely good.  Accepting it is correct — and it
    is the reason "was OCR'd by someone else" cannot itself be the rejection
    rule.
    """
    doc = corpus_doc("dobonov_ocr")
    verdicts = _verdicts(doc, _E8_DOBONOV, "spa")
    assert verdicts[8].is_image_only
    accepted = [i for i, v in verdicts.items()
                if v.accepted and not v.is_image_only]
    assert len(accepted) >= 4, {i: v.reason for i, v in verdicts.items()}
    for i in accepted:
        assert verdicts[i].signals["nonword_ratio"] < 0.10, i


@pytest.mark.golden
def test_cyrillic_pages_are_not_rejected_for_being_cyrillic(corpus_doc):
    """The regression this front's own measurement found, and Sol §SOL-9.

    The n-gram model used to be trained on Latin bigrams only, so on an E6
    page both lexical signals reported "garbage" for a text layer that is
    entirely correct — page 60 of Boleslavsky, a correct table of Russian
    figurine moves, was rejected — and F5 made the terms *abstain* on
    non-Latin text.  Sol §SOL-9 replaced the abstention with a Cyrillic
    model and a Russian list: these pages are now *judged* (the lexical
    terms apply) and accepted on their own evidence, not excused.
    """
    import glob
    import os

    from .conftest import CORPUS_DIR

    matches = glob.glob(os.path.join(
        str(CORPUS_DIR), "*Болесл*.pdf"))
    if not matches:
        pytest.skip("o livro E6 (Boleslávski) não está nesta máquina")

    import pymupdf
    doc = pymupdf.open(matches[0])
    try:
        engine = PdfTextLayerEngine()
        for page in (60, 100, 140, 180, 220):
            if page >= doc.page_count:
                continue
            text = doc[page].get_text()
            profile = script_profile(text)
            assert profile.get("cyrillic", 0) > 0.5 * sum(profile.values()), (
                f"p{page} não é predominantemente cirílica; escolha outra "
                f"página para este teste")
            assert modelled_script_share(text) > 0.90
            verdict = engine.assess(doc[page], lang="rus")
            assert verdict.accepted, (page, verdict.reason)
            # Judged, not excused: the Cyrillic model and list voted.
            assert verdict.signals["lexical_terms_apply"] == 1.0
            assert verdict.signals["ngram_plausibility"] > 0.30
            assert "alfabeto" not in verdict.reason
    finally:
        doc.close()


@requires_font
def test_iter_page_verdicts_pre_flights_a_document():
    """The cheap pass a batch importer runs before rendering anything: which
    pages need OCR at all."""
    from caissa.ocr.engines.pdf_text_layer import iter_page_verdicts

    good = build_pdf()
    verdicts = iter_page_verdicts(good, [0], lang="eng")
    assert [pno for pno, _ in verdicts] == [0]
    assert verdicts[0][1].accepted
    good.close()

    broken = break_tounicode(build_pdf(), mode="dead")
    verdicts = iter_page_verdicts(broken, range(broken.page_count), lang="eng")
    assert verdicts and not verdicts[0][1].accepted
    broken.close()


# --------------------------------------------------------------------------- #
# Is escalating worth it?  (F5_REPORT_C2 §4)
# --------------------------------------------------------------------------- #


#: Two pages per book rather than the eight the benchmark uses, because this
#: runs Tesseract at 300 dpi and the suite pays for it.  The benchmark
#: ``benchmarks/notation_integrity.py --what recovery`` is the wider number.
_RECOVERY_SAMPLE = [
    ("gaprindashvili_ocr", (202, 245), "damaged"),
    ("nunn_pawnless", (120, 200), "damaged"),
    ("dvoretsky", (300, 408), "clean"),
]


@pytest.mark.golden
@pytest.mark.parametrize("key,pages,kind", _RECOVERY_SAMPLE)
def test_escalation_is_justified_by_what_the_engines_actually_do(
        pymupdf, corpus_doc, key, pages, kind):
    """Lowering a damaged page to 0.55 is only right if OCR does better.

    That was left open by the previous cycle and this is the answer.  It is
    not "Tesseract reads the figurines" — it does not, scoring 13-22 % on the
    piece letter.  It is that the **shape** of the two failures differs, and
    only one shape is recoverable:

    ==========================  ============  =============  =========
    book / engine               piece right   1-char error   distinct
    ==========================  ============  =============  =========
    Gaprindashvili · level 0    **0.0 %**     15.1 %         204
    Gaprindashvili · tesseract  12.8 %        **96.7 %**     51
    Nunn · level 0              **0.0 %**     31.2 %         41
    Nunn · tesseract            21.8 %        **98.0 %**     34
    Dvoretsky · level 0         **98.8 %**    98.8 %         7
    Dvoretsky · tesseract       11.3 %        98.4 %         16
    ==========================  ============  =============  =========

    The text layer loses **every** piece letter on the damaged books — 0.0 %
    of 1 274 moves, not "most" — and loses them as 204 distinct noise forms.
    Tesseract loses them as a near-perfect substitution cipher: W for the
    queen, H for the rook, S for the king.  A cipher can be inverted by a
    post-corrector; noise cannot.

    And the control reverses it completely: on Dvoretsky the text layer is
    right 98.8 % of the time and Tesseract collapses to 11.3 %.  **Escalating
    a clean page would be the worse error**, which is why the threshold exists
    and why Dvoretsky never crosses it.

    Measured 2026-09-11 by ``benchmarks/notation_integrity.py --what
    recovery``; the numbers above are its eight-page-per-book run, the
    assertions below its two-page one, with margin.
    """
    import sys

    import numpy as np

    from caissa.ocr.engines.tesseract import TesseractEngine
    from caissa.ocr.types import RegionKind

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve()
                           .parents[3] / "benchmarks"))
    from notation_integrity import piece_prefixes

    engine = TesseractEngine()
    if not engine.available():
        pytest.skip(engine.unavailable_reason() or "Tesseract indisponível")

    doc = corpus_doc(key)
    layer = {"moves": 0, "correct": 0, "single": 0}
    ocr = {"moves": 0, "correct": 0, "single": 0}
    for index in pages:
        page = doc[index]
        pix = page.get_pixmap(dpi=300, colorspace="gray")
        raster = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width)
        for bucket, text in (
                (layer, page.get_text("text") or ""),
                (ocr, engine.recognize(raster, lang="eng",
                                       psm_hint=RegionKind.PAGE).text)):
            moves, single, correct, _ = piece_prefixes(text)
            bucket["moves"] += moves
            bucket["correct"] += correct
            bucket["single"] += single

    assert layer["moves"] >= 40 and ocr["moves"] >= 40, (layer, ocr)

    if kind == "damaged":
        # The text layer loses every single piece letter.  Not "most".
        assert layer["correct"] == 0, (
            f"a camada de texto acertou {layer['correct']} peça(s) num livro "
            f"tido como destruído — reconfira antes de comemorar")
        # And loses them as noise, while Tesseract loses them as a cipher.
        assert layer["single"] / layer["moves"] < 0.55
        assert ocr["single"] / ocr["moves"] > 0.85, (
            "o dano do Tesseract deixou de ser de um caractere só; sem isso "
            "não há corretor de substituição possível")
    else:
        # The control, and the reason the threshold is not lower.
        assert layer["correct"] / layer["moves"] > 0.90
        assert ocr["correct"] / ocr["moves"] < 0.50, (
            "o Tesseract melhorou num livro nativo; se isso virar verdade, "
            "a barra de escalonamento merece ser revista")


@pytest.mark.golden
def test_a_damaged_text_layer_no_longer_beats_tesseract_on_fixed_confidence(
        pymupdf, corpus_doc):
    """**The defect F5_REPORT_C2 §5 recorded, closed by Sol §SOL-4.**

    Until Sol this test asserted the opposite: escalation happened on
    Gaprindashvili p202 — Tesseract ran on the damaged page — but Tesseract
    could not win, because ``EngineCalibration(floor=0.55, gamma=1.4)`` was a
    statement about a single word applied to a page aggregate, and it
    flattened Tesseract's confidence to 0.01–0.07.  The floor was deliberately
    not tuned by eye ("choosing it until Tesseract wins is exactly how a gate
    gets bought") and the state was recorded here.

    Sol §SOL-4 removed the reputation numbers and fits calibration per facet
    on the calibration partition of the golden corpus.  With the neutral
    default (and with the fitted table, when present) Tesseract's calibrated
    confidence on this page is ~0.6 and its score beats the damaged layer's,
    which is what flagging the page at 0.55 was always for.  The region then
    goes to *review*, not to acceptance: 0.73 is under the 0.78 bar, and a
    reviewer sees both readings (Sol §SOL-2).
    """
    import numpy as np

    from caissa.ocr.arbiter import Arbiter, RegionTask
    from caissa.ocr.decision import Decision
    from caissa.ocr.engines.tesseract import TesseractEngine

    engine = TesseractEngine()
    if not engine.available():
        pytest.skip(engine.unavailable_reason() or "Tesseract indisponível")

    doc = corpus_doc("gaprindashvili_ocr")
    page = doc[202]
    pix = page.get_pixmap(dpi=300, colorspace="gray")
    raster = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width)

    outcome = Arbiter([PdfTextLayerEngine(), engine]).run(
        RegionTask(image=raster, pdf_page=page, lang="eng", scale=300.0 / 72.0))

    scores = {s.engine: s for s in outcome.scores}
    assert set(scores) == {"pdf_text_layer", "tesseract"}, (
        "os dois motores precisam ter rodado para esta comparação valer")

    # Tesseract read the page — this is not an empty result.
    assert scores["tesseract"].char_count > 800
    # ...and its language plausibility is *higher* than the damaged layer's.
    assert scores["tesseract"].plausibility > scores["pdf_text_layer"].plausibility

    # And it now wins: the layer's fixed 0.55 no longer outranks a calibrated
    # engine that read the page better.
    assert scores["tesseract"].confidence > 0.40, (
        f"a confiança calibrada do Tesseract voltou a ser esmagada "
        f"({scores['tesseract'].confidence:.3f})")
    assert scores["tesseract"].total > scores["pdf_text_layer"].total
    assert outcome.result.engine == "tesseract"
    assert outcome.decision is not None
    assert outcome.decision.decision in (Decision.REVIEW, Decision.ACCEPTED)
