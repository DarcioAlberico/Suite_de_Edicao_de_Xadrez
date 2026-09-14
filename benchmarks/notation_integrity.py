"""How much of this collection's chess notation survived into its text layer?

Every number in ``docs/quality/F5_REPORT_C2.md`` comes from this script, so that
"the notation is damaged" is a measurement and not an impression.

The signal it measures is :func:`caissa.ocr.lexicon.mangled_move_ratio`.  A
figurine font maps the knight to a private code point; when a PDF is re-OCR'd,
or subset without a usable ToUnicode, that code point comes back as whichever
Latin letters sit in the same place — ``♘xe5`` arrives as ``ll'lxe5``.  The
square survives, because file and rank are ordinary Latin; the piece does not.
Nothing else in the level-0 verdict can see this: the prose is the bulk of the
tokens and the prose is perfect, so the dictionary rate, the n-gram model and
the non-word ratio all report a healthy page.

Three reports, selected with ``--what``:

``books``
    The five books the unit tests pin, page by page, with the two clean
    controls that set the threshold.  This is the table that justifies
    ``max_mangled_move_ratio = 0.15``.

``sweep``
    All 50 files of the collection.  This is the one that showed the defect was
    never about two pages: 16 of the 34 books that have a usable text layer
    carry damaged notation, and every one of them used to be accepted at 0.98.

``verdicts``
    What :meth:`PdfTextLayerEngine.assess` now says about the pages the tests
    pin, so a change of behaviour shows up as a diff rather than as a surprise.

``contest``
    **OCR_UI_ROADMAP passo 2 — does contesting the kept layer pay?**  The
    importer is run twice on the same fixed pages, with
    ``PdfImportOptions.ocr_contests_text_layer`` off and on, and the IR's text
    is compared: moves with a piece (:func:`piece_prefixes`, figurines
    counted as correct), moves that appear only on one side (the invention
    signal), and — on the two clean controls, where the contest must not
    fire — the number of characters that changed, which has to be zero.
    Needs Tesseract; ~3 s per page.

``recovery``
    **Is escalating to Tesseract worth it?**  Flagging a page at 0.55 only
    helps if the engine that then competes reads the notation better, and that
    was an open question until this ran.  The answer is not "yes" or "no" but
    something more useful: *neither* engine reads the figurines, but Tesseract
    fails as a near-perfect substitution cipher (93-98 % of its errors are one
    character, collapsing onto W/H/S/B) while the text layer fails as noise
    (204 distinct garbage forms on one book).  A cipher is invertible; noise is
    not.  Run it with ``--what recovery``; it needs Tesseract and costs about
    1.1 s per page.

CORPUS.md §5 rule 1 — "median of at least three runs" — does not apply: nothing
here is timed and the measurement is exactly deterministic, so one run *is* the
number.  The elapsed time printed at the end is informational.

Usage::

    .venv\\Scripts\\python.exe benchmarks\\notation_integrity.py --what books
    .venv\\Scripts\\python.exe benchmarks\\notation_integrity.py --what sweep --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from collections import Counter
from typing import Any, Iterable

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from caissa.ocr.lexicon import mangled_move_ratio, normalise_lang  # noqa: E402

#: CORPUS.md §0.  Copyrighted material; it never leaves this machine.
CORPUS_DIR = Path(__import__("os").environ.get(
    "CAISSA_CORPUS_PDF", r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF"))

#: A page with fewer moves than this cannot be judged — the same floor
#: ``TextLayerThresholds.min_moves_for_notation_check`` uses.
MIN_MOVES = 12

#: The books the unit tests pin, with the sampling stride that gives roughly
#: the page counts quoted in the report.  ``step`` rather than random pages:
#: CORPUS.md §5 wants a number that can be re-measured, and a random sample
#: cannot be.
BOOKS: list[tuple[str, str, str, int]] = [
    ("Gaprindashvili E8 (dano conhecido)",
     "Gaprindashvili, Paata - Imagination in Chess. How To Think Creatively"
     " And Avoid Foolish Mistakes (Bastford, 2005) 2p 145p_OCR_Aprimorar_"
     "Aprimorar.pdf", "eng", 3),
    ("Aagaard E1", "AAGAARD - Practical Chess Defence.pdf", "eng", 5),
    ("Nunn E2", "\U0001F4DANunn J. Secrets of Pawnless Endings.pdf", "eng", 5),
    ("Dvoretsky E1 (CONTROLE)",
     "Dvoretsky - Dvoretsky's Endgame Manual (2025).pdf", "eng", 11),
    ("Boleslavsky E6 (CONTROLE)",
     "\U0001F4DA\u0411\u043e\u043b\u0435\u0441\u043b\u0430\u0432\u0441\u043a"
     "\u0438\u0439_\u0418_\u0418\u0437\u0431\u0440\u0430\u043d\u043d\u044b"
     "\u0435_\u043f\u0430\u0440\u0442\u0438\u0438.pdf", "rus", 5),
]

#: Pages the unit tests pin, per book key.
PINNED: dict[str, tuple[str, tuple[int, ...], str]] = {
    "gaprindashvili": (BOOKS[0][1], (28, 72, 115, 158, 202, 245), "eng"),
    "aagaard": (BOOKS[1][1], (74, 100, 148, 222, 260), "eng"),
    "nunn": (BOOKS[2][1], (120, 150, 200, 250), "eng"),
    "dvoretsky": (BOOKS[3][1], (204, 300, 408, 500, 612), "eng"),
    "boleslavsky": (BOOKS[4][1], (30, 45, 60, 75, 90), "rus"),
}


def _open(path: Path):
    import pymupdf
    return pymupdf.open(path)


def _lang_of(name: str) -> str:
    """Best guess at a book's language from its filename.

    Only used by the sweep, and only to load the right word list.  A wrong
    guess costs a little recall on the lexicon exemption, never a false
    positive: the damaged tokens are damaged in every language.
    """
    n = name.lower()
    if any(k in n for k in ("боле", "журав", "левенфиш", "levenfis")):
        return "rus"
    if any(k in n for k in ("combinacion", "ajedrez", "espa", "sacrificios")):
        return "spa"
    if any(k in n for k in ("quebra", "xadrez", "portug", "partidas", "finais")):
        return "por"
    if any(k in n for k in ("mittelspiel", "euwe", "gunderam", "kemeri",
                            "eroeffnung", "neumann")):
        return "deu"
    if any(k in n for k in ("blind schaken", "zwarte magie", "niemeijer",
                            "meestertournooi")):
        return "nld"
    return "eng"


def scan(path: Path, lang: str, *, step: int, cap: int) -> list[dict[str, Any]]:
    """Sampled pages of one book, with their damaged-move ratio.

    ``step=0`` spreads the sample over the whole book instead of reading the
    first ``cap`` pages, which on most of this collection are front matter and
    carry no moves at all.
    """
    langs = normalise_lang(lang)
    doc = _open(path)
    rows: list[dict[str, Any]] = []
    stride = step if step > 0 else max(1, doc.page_count // max(1, cap))
    try:
        for index in range(0, doc.page_count, stride):
            if len(rows) >= cap:
                break
            try:
                text = doc[index].get_text("text") or ""
            except Exception:                       # a page that will not open
                continue
            ratio, moves = mangled_move_ratio(text, langs)
            if moves < MIN_MOVES:
                continue
            rows.append({"page": index, "moves": moves, "ratio": ratio})
    finally:
        doc.close()
    return rows


def _quantiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {}
    return {
        "median": ordered[len(ordered) // 2],
        "min": ordered[0],
        "p90": ordered[int(0.9 * (len(ordered) - 1))],
        "max": ordered[-1],
    }


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #


def report_books(cap: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    print(f"{'livro':34s} {'pgs':>4s} {'mediana':>8s} {'min':>7s} "
          f"{'p90':>7s} {'max':>7s}  >0,15")
    for label, name, lang, step in BOOKS:
        path = CORPUS_DIR / name
        if not path.is_file():
            print(f"{label:34s}  AUSENTE")
            continue
        rows = scan(path, lang, step=step, cap=cap)
        ratios = [r["ratio"] for r in rows]
        q = _quantiles(ratios)
        if not q:
            print(f"{label:34s}  nenhuma página com >= {MIN_MOVES} lances")
            continue
        over = sum(1 for r in ratios if r > 0.15)
        print(f"{label:34s} {len(rows):4d} {q['median']:8.3f} {q['min']:7.3f} "
              f"{q['p90']:7.3f} {q['max']:7.3f}  {over:3d}/{len(rows)}")
        out[label] = {"pages": len(rows), "over_threshold": over, **q}
    return out


def report_sweep(cap: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    buckets = {"damaged": 0, "marginal": 0, "clean": 0, "no_layer": 0}
    print(f"{'':4s} {'pgs':>4s} {'mediana':>8s} {'max':>7s}  livro")
    scanned = []
    for path in sorted(CORPUS_DIR.glob("*.pdf")):
        try:
            rows = scan(path, _lang_of(path.name), step=0, cap=cap)
        except Exception as exc:                     # a file that will not open
            print(f"!!   {path.name[:62]}  ({exc})")
            continue
        scanned.append((path.name, rows))
    for name, rows in scanned:
        ratios = [r["ratio"] for r in rows]
        q = _quantiles(ratios)
        if not q:
            buckets["no_layer"] += 1
            print(f"{'—':4s} {'—':>4s} {'—':>8s} {'—':>7s}  {name[:62]}  "
                  f"(sem camada de texto com lances)")
            out[name] = {"pages": 0, "verdict": "no_layer"}
            continue
        if q["median"] > 0.10:
            mark, verdict = "DAN ", "damaged"
        elif q["median"] > 0.03:
            mark, verdict = "...  ", "marginal"
        else:
            mark, verdict = "ok  ", "clean"
        buckets[verdict] += 1
        print(f"{mark:4s} {len(rows):4d} {q['median']:8.3f} {q['max']:7.3f}  "
              f"{name[:62]}")
        out[name] = {"pages": len(rows), "verdict": verdict, **q}
    print(f"\nlivros: {buckets['damaged']} com notação danificada · "
          f"{buckets['marginal']} marginais · {buckets['clean']} limpos · "
          f"{buckets['no_layer']} sem camada de texto")
    out["_buckets"] = buckets
    return out


def report_verdicts() -> dict[str, Any]:
    from caissa.ocr.engines.pdf_text_layer import PdfTextLayerEngine

    engine = PdfTextLayerEngine()
    out: dict[str, Any] = {}
    for key, (name, pages, lang) in PINNED.items():
        path = CORPUS_DIR / name
        if not path.is_file():
            print(f"--- {key}: AUSENTE")
            continue
        print(f"--- {key}")
        doc = _open(path)
        try:
            for page in pages:
                if page >= doc.page_count:
                    continue
                verdict = engine.assess(doc[page], lang=lang)
                s = verdict.signals
                print(f"   p{page:4d} aceita={str(verdict.accepted):5s} "
                      f"conf={verdict.confidence:.2f} "
                      f"danificados={s['mangled_move_ratio']:.3f}"
                      f"/{s['moves_judged']:.0f}  "
                      f"nonword={s['nonword_ratio']:.3f} "
                      f"dict={s['dictionary_hit_rate']:.2f}")
                out[f"{key}:{page}"] = {
                    "accepted": verdict.accepted,
                    "confidence": verdict.confidence,
                    "mangled_move_ratio": s["mangled_move_ratio"],
                    "moves_judged": s["moves_judged"],
                }
        finally:
            doc.close()
    return out


# --------------------------------------------------------------------------- #
# Recoverability
# --------------------------------------------------------------------------- #

#: The body of a move after the piece letter: optional disambiguation, an
#: optional capture mark, the destination square, optional promotion and marks.
#: Deliberately permissive about the promotion letter, because an engine that
#: mangles the piece glyph mangles the promotion glyph the same way.
_MOVE_TAIL = re.compile(
    r"(?:[a-h]?[1-8]?[x:×-]?[a-h][1-8](?:=[A-Za-z])?[+#!?]{0,3})$")

#: A move number glued to the move — ``4.Kd3``, ``1...Nf6``.  Not part of the
#: piece glyph, and counting it would penalise both engines for nothing.
_MOVE_NUMBER = re.compile(r"^\d{1,3}\.{1,3}")

#: The figurines a fused reading may carry instead of the letter (the glyph
#: reader and the fine-tuned model emit them): the piece survived too.
_FIGURINES = frozenset("♔♕♖♗♘♙")

#: The piece letters an English-language book actually uses.  The question here
#: is "did the glyph survive", so the answer has to be checked against real
#: notation, not against the permissive multilingual set.
_ENGLISH_PIECES = frozenset("KQRBNP")

#: Pages sampled per book.  Fixed, so the number can be re-measured.
RECOVERY_PAGES: list[tuple[str, str, list[int]]] = [
    ("Gaprindashvili E8", PINNED["gaprindashvili"][0],
     [158, 170, 190, 202, 210, 230, 245, 250]),
    ("Aagaard E1", PINNED["aagaard"][0], [148, 170, 200, 222, 240, 260]),
    ("Nunn E2", PINNED["nunn"][0], [120, 140, 160, 180, 200, 220]),
    ("Dvoretsky E1 (CONTROLE)", PINNED["dvoretsky"][0], [204, 300, 408, 500]),
]


def piece_prefixes(text: str) -> tuple[int, int, int, Counter[str]]:
    """``(moves, single_char, correct_piece, prefix histogram)``.

    A "move with a piece" is a token ending in a well-formed move body and
    carrying something in front of it.  Pawn moves are excluded: they have no
    piece glyph to lose, so counting them would flatter whichever engine reads
    more pawn moves.
    """
    prefixes: Counter[str] = Counter()
    moves = single = correct = 0
    for raw in text.split():
        token = raw.strip("(),;")
        match = _MOVE_TAIL.search(token)
        if match is None or match.start() == len(token):
            continue
        prefix = _MOVE_NUMBER.sub("", token[:match.start()])
        if not prefix:
            continue
        moves += 1
        prefixes[prefix] += 1
        if len(prefix) == 1:
            single += 1
        if prefix in _ENGLISH_PIECES or prefix in _FIGURINES:
            correct += 1
    return moves, single, correct, prefixes


def report_recovery() -> dict[str, Any]:
    import numpy as np

    from caissa.ocr.engines.tesseract import TesseractEngine
    from caissa.ocr.types import RegionKind

    engine = TesseractEngine()
    if not engine.available():
        print(f"Tesseract indisponível: {engine.unavailable_reason()}")
        return {}

    out: dict[str, Any] = {}
    print(f"{'livro / motor':34s} {'lances':>7s} {'peça certa':>11s} "
          f"{'1 caractere':>12s} {'formas':>7s}")
    for label, name, pages in RECOVERY_PAGES:
        path = CORPUS_DIR / name
        if not path.is_file():
            print(f"{label:34s}  AUSENTE")
            continue
        doc = _open(path)
        totals = {k: [0, 0, 0, Counter()] for k in ("nível 0", "tesseract")}
        try:
            for index in pages:
                if index >= doc.page_count:
                    continue
                page = doc[index]
                rows = [("nível 0", page.get_text("text") or "")]
                pix = page.get_pixmap(dpi=300, colorspace="gray")
                raster = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width)
                rows.append(("tesseract", engine.recognize(
                    raster, lang="eng", psm_hint=RegionKind.PAGE).text))
                for who, text in rows:
                    m, s, c, pre = piece_prefixes(text)
                    totals[who][0] += m
                    totals[who][1] += s
                    totals[who][2] += c
                    totals[who][3].update(pre)
        finally:
            doc.close()
        print(f"  {label}")
        for who, (moves, single, correct, pre) in totals.items():
            if not moves:
                print(f"    {who:30s}  sem lances com peça")
                continue
            print(f"    {who:30s} {moves:7d} {correct / moves:10.1%} "
                  f"{single / moves:11.1%} {len(pre):7d}")
            print(f"      {', '.join(f'{k!r}×{v}' for k, v in pre.most_common(6))}")
            out[f"{label}:{who}"] = {
                "moves": moves,
                "correct_piece": correct / moves,
                "single_char_prefix": single / moves,
                "distinct_forms": len(pre),
                "top": pre.most_common(8),
            }
    return out


# --------------------------------------------------------------------------- #
# OCR_UI_ROADMAP passo 2: the contested layer, end to end through the importer
# --------------------------------------------------------------------------- #

#: Fixed pages per book for ``--what contest``: the damaged books of
#: ``RECOVERY_PAGES`` and the two clean controls (the contest must not fire).
CONTEST_PAGES: list[tuple[str, str, str, list[int], bool]] = [
    ("Gaprindashvili E8", PINNED["gaprindashvili"][0], "eng",
     [158, 170, 190, 202, 210, 230, 245, 250], False),
    ("Aagaard E1", PINNED["aagaard"][0], "eng", [148, 170, 200, 222, 240, 260], False),
    ("Nunn E2", PINNED["nunn"][0], "eng", [120, 140, 160, 180, 200, 220], False),
    ("Dvoretsky E1 (CONTROLE)", PINNED["dvoretsky"][0], "eng", [204, 300, 408, 500], True),
    ("Boleslavsky E6 (CONTROLE)", PINNED["boleslavsky"][0], "rus", [30, 45, 60, 75], True),
]

_PIECE_MOVE = re.compile(r"^(?:\d{1,3}\.{1,3})?([KQRBNP♔♕♖♗♘♙])([a-h]?[1-8]?[x:×]?[a-h][1-8])"
                         r"(?:=[A-Za-z])?[+#!?]{0,3}$")


def _piece_moves(text: str) -> Counter[str]:
    """Well-formed piece moves, normalised (figurine → letter), with multiplicity."""
    figurine_to_letter = dict(zip("♔♕♖♗♘♙", "KQRBNP", strict=True))
    out: Counter[str] = Counter()
    for raw in text.split():
        match = _PIECE_MOVE.match(raw.strip("(),;"))
        if match:
            piece = figurine_to_letter.get(match.group(1), match.group(1))
            out[piece + match.group(2)] += 1
    return out


_MOVEISH_TOKEN = re.compile(r"^[^\s]*[a-h][1-8][+#!?]{0,3}$|^\d{1,3}\.{0,3}$|^[O0]-[O0](?:-[O0])?[+#!?]*$")


def _prose_only(text: str) -> str:
    """The prose words alone: alphabetic tokens of three or more letters.

    Move-shaped tokens go, but so does the *damaged* notation on both sides
    (``'it?dl``, ``Scl``, ``WIS?!``), which no move pattern matches and which
    would otherwise be counted as prose the OCR "changed".  What is left is
    what a reader reads as words, and that is what must survive the contest.
    """
    words = []
    for raw in text.split():
        token = raw.strip("(),;.:!?\"'—–-")
        if len(token) >= 3 and token.isalpha() and not _MOVEISH_TOKEN.match(token):
            words.append(token)
    return " ".join(words)


def _prose_cer(reference: str, hypothesis: str) -> float:
    """Character error rate of the prose against the layer's own prose."""
    from caissa.ocr.metrics import normalise, score_text

    ref, hyp = normalise(_prose_only(reference)), normalise(_prose_only(hypothesis))
    if not ref:
        return 0.0
    return float(score_text(ref, hyp).cer)


def _page_texts(path: Path, pages: list[int], lang: str, *, contest: bool) -> dict[int, str]:
    from caissa.core.model import Heading, Paragraph, plain_text
    from caissa.ingest.pdf.importer import PdfImportOptions, import_pdf

    options = PdfImportOptions(pages=pages, lang=lang, detect_diagrams=False,
                               ocr_contests_text_layer=contest)
    result = import_pdf(path, options)
    texts: dict[int, list[str]] = {p: [] for p in pages}
    for block in result.document.body:
        if not isinstance(block, (Paragraph, Heading)) or block.provenance is None:
            continue
        page = block.provenance.page_index
        if page in texts:
            texts[page].append(plain_text(block.content))
    sources = {r.index: r.source for r in result.report.pages}
    return {p: "\n".join(t) for p, t in texts.items()}, sources


def report_contest() -> dict[str, Any]:
    from caissa.ocr.engines.tesseract import TesseractEngine

    if not TesseractEngine().available():
        print("Tesseract indisponível")
        return {}
    out: dict[str, Any] = {}
    print(f"{'livro':30s} {'pág.':>5s} {'fonte':16s} {'lances c/ peça':>14s} "
          f"{'peça certa':>11s} {'só sem':>6s} {'só com':>6s} {'chars Δ':>8s} {'CER prosa':>9s}")
    for label, name, lang, pages, control in CONTEST_PAGES:
        path = CORPUS_DIR / name
        if not path.is_file():
            print(f"{label:30s}  AUSENTE")
            continue
        before, _ = _page_texts(path, pages, lang, contest=False)
        after, sources = _page_texts(path, pages, lang, contest=True)
        totals = {"moves_before": 0, "correct_before": 0, "moves_after": 0,
                  "correct_after": 0, "only_before": 0, "only_after": 0, "chars_changed": 0,
                  "contested": 0, "prose_cer_sum": 0.0}
        for page in pages:
            b, a = before.get(page, ""), after.get(page, "")
            mb, _, cb, _ = piece_prefixes(b)
            ma, _, ca, _ = piece_prefixes(a)
            pb, pa = _piece_moves(b), _piece_moves(a)
            only_b = sum((pb - pa).values())
            only_a = sum((pa - pb).values())
            changed = (0 if b == a else
                       sum(1 for x, y in zip(b, a, strict=False) if x != y) + abs(len(a) - len(b)))
            src = sources.get(page, "?")
            prose_cer = _prose_cer(b, a) if src == "text-layer+ocr" else 0.0
            totals["moves_before"] += mb
            totals["correct_before"] += cb
            totals["moves_after"] += ma
            totals["correct_after"] += ca
            totals["only_before"] += only_b
            totals["only_after"] += only_a
            totals["chars_changed"] += changed
            totals["contested"] += int(src == "text-layer+ocr")
            totals["prose_cer_sum"] += prose_cer
            print(f"{label:30s} {page:5d} {src:16s} {mb:6d} → {ma:5d} "
                  f"{(cb / mb if mb else 0):4.0%} → {(ca / ma if ma else 0):4.0%} "
                  f"{only_b:6d} {only_a:6d} {changed:8d} {prose_cer:8.3f}")
        verdict = ""
        if control:
            intact = totals["chars_changed"] == 0 and totals["contested"] == 0
            verdict = "  ✓ controle intacto" if intact else "  ✗ CONTROLE ALTERADO"
        print(f"  {label}: lances c/ peça {totals['moves_before']} → {totals['moves_after']}, "
              f"peça certa {totals['correct_before']} → {totals['correct_after']}, "
              f"só sem {totals['only_before']}, só com {totals['only_after']}, "
              f"páginas contestadas {totals['contested']}/{len(pages)}, "
              f"CER médio da prosa nas contestadas "
              f"{(totals['prose_cer_sum'] / totals['contested']) if totals['contested'] else 0.0:.3f}"
              f"{verdict}")
        out[label] = totals
    return out


# --------------------------------------------------------------------------- #
# What the decoder recovers
# --------------------------------------------------------------------------- #

#: Anything shaped like a move, whatever sits in the piece slot.
_MOVEISH = re.compile(r"[^\W\d_?&@%][a-h]?[1-8]?[x:×-]?[a-h][1-8][+#!?]{0,3}$")


def _readability(text: str) -> tuple[int, int, int]:
    """``(valid SAN, destination known but piece unknown, unreadable)``."""
    from caissa.notation.languages import parse_san
    from caissa.ocr.notation import CIPHER_SLOT

    valid = slotted = unreadable = 0
    for raw in text.split():
        token = _MOVE_NUMBER.sub("", raw.strip("(),;:."))
        if not _MOVEISH.match(token) and not token.startswith(CIPHER_SLOT):
            continue
        if parse_san(token) is not None:
            valid += 1
        elif token.startswith(CIPHER_SLOT):
            slotted += 1
        else:
            unreadable += 1
    return valid, slotted, unreadable


def report_decode() -> dict[str, Any]:
    import numpy as np

    from caissa.ocr.engines.tesseract import TesseractEngine
    from caissa.ocr.notation import decode, infer_cipher
    from caissa.ocr.types import RegionKind

    engine = TesseractEngine()
    if not engine.available():
        print(f"Tesseract indisponível: {engine.unavailable_reason()}")
        return {}

    out: dict[str, Any] = {}
    print("SOBRE A SAÍDA DO TESSERACT — livros com a notação destruída")
    for label, name, pages in RECOVERY_PAGES[:3]:
        path = CORPUS_DIR / name
        if not path.is_file():
            print(f"  {label}: AUSENTE")
            continue
        doc = _open(path)
        before = [0, 0, 0]
        after = [0, 0, 0]
        flagged = 0
        try:
            for index in pages:
                if index >= doc.page_count:
                    continue
                pix = doc[index].get_pixmap(dpi=300, colorspace="gray")
                raster = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width)
                text = engine.recognize(raster, lang="eng",
                                        psm_hint=RegionKind.PAGE).text
                report = infer_cipher(text)
                flagged += int(report.is_ciphered)
                for i, value in enumerate(_readability(text)):
                    before[i] += value
                for i, value in enumerate(_readability(decode(text, report))):
                    after[i] += value
        finally:
            doc.close()
        total = sum(before) or 1
        print(f"  {label}  ({len(pages)} páginas, {flagged} acusadas de cifra)")
        print(f"    antes : SAN {before[0]:4d} ({before[0]/total:5.1%})  "
              f"peça ? {before[1]:4d}  ilegível {before[2]:4d} "
              f"({before[2]/total:5.1%})")
        print(f"    depois: SAN {after[0]:4d} ({after[0]/total:5.1%})  "
              f"peça ? {after[1]:4d} ({after[1]/total:5.1%})  "
              f"ilegível {after[2]:4d} ({after[2]/total:5.1%})")
        out[label] = {"before": before, "after": after, "flagged": flagged}

    print()
    print("SOBRE A CAMADA DE TEXTO — controles, nada pode mudar")
    for key, pages in (("dvoretsky", (204, 300, 408, 500, 612)),
                       ("boleslavsky", (30, 45, 60, 75, 90))):
        name = PINNED[key][0] if key in PINNED else None
        if name is None:
            continue
        path = CORPUS_DIR / name
        if not path.is_file():
            print(f"  {key}: AUSENTE")
            continue
        doc = _open(path)
        intact = checked = 0
        try:
            for index in pages:
                if index >= doc.page_count:
                    continue
                text = doc[index].get_text("text") or ""
                if not text.strip():
                    continue
                checked += 1
                intact += int(decode(text, infer_cipher(text)) == text)
        finally:
            doc.close()
        mark = "ok" if intact == checked else "!!"
        print(f"  {mark} {key:16s} {intact}/{checked} páginas intactas")
        out[f"controle:{key}"] = {"intact": intact, "checked": checked}
    return out


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.split("\n")[0])
    parser.add_argument(
        "--what",
        choices=("books", "sweep", "verdicts", "recovery", "decode", "contest", "all"),
        default="books")
    parser.add_argument("--cap", type=int, default=60,
                        help="máximo de páginas amostradas por livro")
    parser.add_argument("--json", type=Path, default=None,
                        help="grava os números num arquivo, para diferença")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not CORPUS_DIR.is_dir():
        print(f"o acervo local não está em {CORPUS_DIR} "
              f"(docs/quality/CORPUS.md §0). Aponte CAISSA_CORPUS_PDF.",
              file=sys.stderr)
        return 2

    started = time.perf_counter()
    results: dict[str, Any] = {}
    if args.what in ("books", "all"):
        results["books"] = report_books(args.cap)
    if args.what in ("sweep", "all"):
        if results:
            print()
        # The sweep spreads its sample over the whole book rather than reading
        # the first pages, which are front matter and carry no moves.
        results["sweep"] = report_sweep(args.cap)
    if args.what in ("verdicts", "all"):
        if results:
            print()
        results["verdicts"] = report_verdicts()
    if args.what in ("recovery", "all"):
        if results:
            print()
        results["recovery"] = report_recovery()
    if args.what in ("decode", "all"):
        if results:
            print()
        results["decode"] = report_decode()
    if args.what in ("contest", "all"):
        if results:
            print()
        results["contest"] = report_contest()

    print(f"\n{time.perf_counter() - started:.1f} s")
    if args.json is not None:
        args.json.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        print(f"números gravados em {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
