"""B10/G7 (ciclo 2): the figurine keeps its set and says who put it there.

Two losses the analysis named (``OCR_UI_ANALISE_C2.md`` §5.7): ``PieceGlyph`` was built
without ``figurine_set`` (so ``♕`` came out ``♛`` in the DOCX/EPUB) and without a
provenance of its own; and ``to_page_text`` collapsed the line into one span with the
line's worst confidence, so the review could not tell a figurine the glyph reader saw at
0,99 from one the book cipher inferred.
"""

from __future__ import annotations

from caissa.core.chess.notation_tables import FigurineSet, PieceType
from caissa.core.model import PieceGlyph, Provenance, SourceKind, Text, plain_text
from caissa.export.text import inline_plain_text as inline_text
from caissa.ingest.pdf.geometry import PageFrame
from caissa.ingest.pdf.importer import _span_inlines
from caissa.ingest.pdf.ocr_service import RegionRecognition, _figurine_origins, _line_spans
from caissa.ingest.pdf.textlayer import CIPHER_ORIGIN, TextSpan
from caissa.ocr.decision import Decision, RegionDecision
from caissa.ocr.types import BBox, OcrLine, OcrResult, OcrWord, RegionKind


def _span(text: str, **extra) -> TextSpan:
    return TextSpan(text=text, box=(0.0, 0.0, 10.0, 10.0), **extra)


def test_the_glyph_keeps_the_set_it_was_printed_in():
    nodes = _span_inlines(_span("♕d5 ♛xe5"))
    glyphs = [n for n in nodes if isinstance(n, PieceGlyph)]
    assert [g.piece for g in glyphs] == [PieceType.QUEEN, PieceType.QUEEN]
    assert [g.figurine_set for g in glyphs] == [FigurineSet.WHITE, FigurineSet.BLACK]
    # The printed form survives to the export: an outline queen stays outline.
    assert inline_text(nodes) == "♕d5 ♛xe5"
    # The IR's letter form is set-blind by design (``plain_text`` prints letters).
    assert plain_text(nodes) == "Qd5 Qxe5"


def test_the_glyph_carries_its_own_provenance_with_the_reader_and_the_note():
    seen: list[tuple[str, str]] = []

    def provenance(span: TextSpan, note: str) -> Provenance:
        seen.append((span.engine, note))
        return Provenance(kind=SourceKind.OCR, engine=span.engine or None,
                          confidence=span.confidence, note=note)

    read = _span_inlines(_span("♖e8!", engine="tesseract", figurine_origin="glyph",
                               confidence=0.99), provenance)
    inferred = _span_inlines(_span("♕d5", engine="tesseract", figurine_origin=CIPHER_ORIGIN,
                                   confidence=0.61), provenance)
    own = _span_inlines(_span("♘f3", engine="rapidocr", confidence=0.8), provenance)
    layer = _span_inlines(_span("♘f3", confidence=1.0), provenance)
    glyph = next(n for n in read if isinstance(n, PieceGlyph))
    # The block's engine is the OCR that read the words (Sol §SOL-10); the note says who
    # put the piece there.
    assert glyph.provenance is not None and glyph.provenance.engine == "tesseract"
    assert glyph.provenance.confidence == 0.99
    assert "leitor de glifos" in glyph.provenance.note
    cipher = next(n for n in inferred if isinstance(n, PieceGlyph))
    assert "cifra" in cipher.provenance.note and "não lida" in cipher.provenance.note
    assert cipher.provenance.confidence == 0.61
    assert "lida por rapidocr" in next(n for n in own if isinstance(n, PieceGlyph)).provenance.note
    assert "camada de texto" in next(n for n in layer if isinstance(n, PieceGlyph)).provenance.note
    # Plain text runs stay plain: no provenance factory call for them.
    assert all(isinstance(n, (Text, PieceGlyph)) for n in read + inferred + own + layer)
    assert len(seen) == 4


def _region(words: list[tuple[str, float]], meta: dict) -> RegionRecognition:
    ocr_words = tuple(OcrWord(text=t, box=BBox(10.0 + 60.0 * i, 8.0, 50.0, 18.0), confidence=c,
                              word_index=i) for i, (t, c) in enumerate(words))
    line = OcrLine(words=ocr_words, box=BBox(10.0, 8.0, 60.0 * len(words), 18.0), font_size=18.0)
    result = OcrResult(engine="tesseract", lang="eng", lines=(line,), region_kind=RegionKind.MOVETEXT,
                       meta=meta)
    decision = RegionDecision(Decision.ACCEPTED, 0.9, 0.78, 0.55, ())
    return RegionRecognition(reading_order=0, kind=RegionKind.MOVETEXT, box_px=line.box,
                             result=result, decision=decision, engine="tesseract", variant="original",
                             score=0.9)


def test_figurine_words_become_their_own_spans_with_origin_and_confidence():
    meta = {
        "fusion_tokens": [{"text": "♖e8!", "from": "original/glyph", "confidence": 0.97}],
        "book_cipher_applied": {"Wd5": "♕d5"},
    }
    region = _region([("36...", 0.9), ("♖e8!", 0.97), ("37", 0.9), ("♕d5", 0.6), ("wins", 0.9)], meta)
    assert _figurine_origins(region) == {"♖e8!": "glyph", "♕d5": CIPHER_ORIGIN}
    frame = PageFrame.synthetic(3, 288.0, 96.0)
    line = region.result.lines[0]
    spans = _line_spans(line, line.text, (0.0, 0.0, 100.0, 5.0), 4.0, region, False,
                        _figurine_origins(region), frame, 300.0)
    assert [s.text for s in spans] == ["36... ", "♖e8! ", "37 ", "♕d5 ", "wins"]
    assert "".join(s.text for s in spans) == line.text
    # Every span keeps the engine that read the words; the figurine word says who put the
    # piece there (the block's provenance stays the OCR's, Sol §SOL-1/§SOL-10).
    assert [s.engine for s in spans] == ["tesseract"] * 5
    assert [s.figurine_origin for s in spans] == ["", "glyph", "", CIPHER_ORIGIN, ""]
    assert spans[1].confidence == 0.97 and spans[3].confidence == 0.6
    # A line without figurines is one span, as before.
    plain = _region([("White", 0.9), ("wins", 0.8)], {})
    line = plain.result.lines[0]
    assert len(_line_spans(line, line.text, (0.0, 0.0, 100.0, 5.0), 4.0, plain, False, {}, frame,
                           300.0)) == 1
