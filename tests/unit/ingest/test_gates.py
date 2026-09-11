"""The F2 gates (docs/ROADMAP.md), each with its proof of vitality.

A gate that only ever reports green is indistinguishable from a blind gate
(HANDOFF section 7, sixteen times over).  So every gate here is run twice:
once on the product, and once on a deliberately broken version of it that
the gate must catch.

1. A 500-page PDF: first page in at most 2 s.
2. Memory stable over a full scan: no linear growth with page count.
3. Reading order correct on 100 % of two-column pages.
"""

from __future__ import annotations

import ctypes
import gc
import random
import sys
import time

import pytest

from caissa.ingest.pdf import PdfImportOptions, import_pdf, open_pdf
from caissa.ingest.pdf.render import PageRenderer, RenderCache
from caissa.ingest.pdf.textlayer import extract_page_text

from .conftest import (
    LOREM,
    LOREM_EN,
    PageSpec,
    build_pdf,
    lines_of,
    paragraphs_of,
    requires_pymupdf,
    two_column_page,
)

pytestmark = [requires_pymupdf, pytest.mark.slow]

FIRST_PAGE_BUDGET_S = 2.0
MEMORY_GROWTH_BUDGET_MB = 25.0


# --------------------------------------------------------------------------- #
# Gate 1: first page of a 500-page book
# --------------------------------------------------------------------------- #


def _big_book(pages: int, tmp_path):
    specs = []
    for n in range(pages):
        spec = PageSpec()
        spec.items.extend(lines_of(f"Página {n}. {LOREM} {LOREM_EN}", x=72, y=90, width_chars=70))
        spec.items.extend(lines_of(f"{LOREM_EN} {LOREM}", x=72, y=200, width_chars=70))
        specs.append(spec)
    target = tmp_path / f"livro-{pages}.pdf"
    target.write_bytes(build_pdf(specs))
    return target


def test_first_page_of_a_500_page_book_within_two_seconds(tmp_path):
    path = _big_book(500, tmp_path)
    started = time.perf_counter()
    with open_pdf(path) as doc:
        opened = time.perf_counter() - started
        assert doc.page_count == 500
        renderer = PageRenderer(doc, RenderCache(64 * 1024 * 1024))
        rendered = renderer.render(0, dpi=150)
        frame = doc.frame(0)
        with doc.locked() as raw:
            text = extract_page_text(raw[0], frame)
    elapsed = time.perf_counter() - started
    assert rendered.image.shape[0] > 0
    assert text.char_count > 0
    assert elapsed <= FIRST_PAGE_BUDGET_S, (
        f"primeira página em {elapsed:.2f} s (abertura {opened:.3f} s)"
    )


def test_first_page_gate_sees_a_slow_open(tmp_path, monkeypatch):
    """Vitality: an open that walks every page must be caught."""
    path = _big_book(500, tmp_path)
    import caissa.ingest.pdf.document as document_module

    real_open = document_module.open_pdf

    def slow_open(source):
        doc = real_open(source)
        with doc.locked() as raw:
            for page in raw:  # touch every page, the way a naive loader would
                page.get_text("dict")
                page.get_pixmap(dpi=200)
        return doc

    monkeypatch.setattr(document_module, "open_pdf", slow_open)
    started = time.perf_counter()
    with document_module.open_pdf(path):
        pass
    elapsed = time.perf_counter() - started
    assert elapsed > FIRST_PAGE_BUDGET_S * 0.5, "a sabotagem deveria custar tempo visível"


# --------------------------------------------------------------------------- #
# Gate 2: memory stable over a full scan
# --------------------------------------------------------------------------- #


def _working_set_mb() -> float:
    """Resident set size of this process, in MB."""
    if sys.platform == "win32":

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(Counters),
            ctypes.c_ulong,
        ]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        handle = kernel32.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            pytest.skip(f"GetProcessMemoryInfo falhou: erro {ctypes.get_last_error()}")
        return counters.WorkingSetSize / (1024 * 1024)
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except ImportError:  # pragma: no cover
        pytest.skip("sem medidor de memória nesta plataforma")


def _settle() -> float:
    import pymupdf

    gc.collect()
    pymupdf.TOOLS.store_shrink(100)  # empty MuPDF's own cache: measure *our* retention
    return _working_set_mb()


def _picture_book(pages: int, tmp_path):
    """Pages that are cheap as text and expensive as objects: a raster each."""
    specs = []
    for n in range(pages):
        spec = PageSpec(images=[(72.0, 300.0, 540.0, 700.0, 640, 560)])
        spec.items.extend(lines_of(f"Página {n}. {LOREM}", x=72, y=90, width_chars=70))
        specs.append(spec)
    target = tmp_path / f"figuras-{pages}.pdf"
    target.write_bytes(build_pdf(specs))
    return target


def test_memory_does_not_grow_with_the_page_count(tmp_path):
    path = _picture_book(240, tmp_path)
    samples: dict[int, float] = {}

    def progress(done: int, total: int) -> None:
        # The build pass runs from ``total/2`` to ``total``.
        if done in (total // 2 + 40, total):
            samples[done] = _settle()

    import_pdf(path, PdfImportOptions(progress=progress, detect_diagrams=False))
    assert len(samples) == 2, samples
    first, last = (samples[k] for k in sorted(samples))
    growth = last - first
    assert growth < MEMORY_GROWTH_BUDGET_MB, f"cresceu {growth:.1f} MB entre a página 40 e a 240"


def test_memory_gate_sees_a_leak(tmp_path):
    """Vitality: an importer that keeps every page's pixmap must be caught."""
    path = _picture_book(240, tmp_path)
    hoard: list[object] = []
    samples: dict[int, float] = {}

    def leaky_finder(page, _frame, _text):
        hoard.append(page.get_pixmap(dpi=150))  # the leak: 1,4 MB per page, kept
        return []

    def progress(done: int, total: int) -> None:
        if done in (total // 2 + 40, total):
            samples[done] = _settle()

    import_pdf(path, PdfImportOptions(progress=progress, diagram_finder=leaky_finder))
    first, last = (samples[k] for k in sorted(samples))
    assert last - first > MEMORY_GROWTH_BUDGET_MB, "o medidor não viu 200 pixmaps retidos"
    hoard.clear()


# --------------------------------------------------------------------------- #
# Gate 3: reading order on two-column pages
# --------------------------------------------------------------------------- #

SENTENCES = [
    "O rei deve centralizar-se no final.",
    "A torre pertence atrás do peão passado.",
    "Dois bispos valem mais em posições abertas.",
    "O cavalo é forte numa casa avançada protegida.",
    "A dama não deve sair cedo demais.",
    "Peões dobrados são fracos sem contrapartida.",
    "A oposição decide finais de peões.",
    "Zugzwang é a arma do final.",
]


def _two_column_book(seed: int, pages: int):
    rng = random.Random(seed)
    specs = []
    expected_pages = []
    for n in range(pages):
        left = [
            " ".join(rng.sample(SENTENCES, 3)) + f" ({n}-{k})" for k in range(rng.randint(2, 3))
        ]
        right = [
            " ".join(rng.sample(SENTENCES, 3)) + f" ({n}-{k + 5})" for k in range(rng.randint(2, 3))
        ]
        spec, expected = two_column_page(
            left,
            right,
            heading=f"Capítulo {n + 1}" if rng.random() < 0.4 else None,
            footnote=f"Nota {n}." if rng.random() < 0.5 else None,
            running_head="Estratégia em duas colunas",
            folio=n + 1,
            hyphenate=rng.random() < 0.5,
        )
        specs.append(spec)
        expected_pages.append(expected)
    return build_pdf(specs), expected_pages


def _order_score(document, expected_pages):
    got = paragraphs_of(document)
    cursor = 0
    correct = 0
    for expected in expected_pages:
        window = got[cursor : cursor + len(expected)]
        if window == expected:
            correct += 1
        cursor += len(expected)
    return correct, len(expected_pages), got


def test_reading_order_is_correct_on_every_two_column_page(tmp_path):
    blob, expected_pages = _two_column_book(seed=7, pages=40)
    path = tmp_path / "colunas.pdf"
    path.write_bytes(blob)
    result = import_pdf(path, PdfImportOptions(detect_diagrams=False))
    correct, total, got = _order_score(result.document, expected_pages)
    assert correct == total, f"{correct}/{total} páginas na ordem certa; começo: {got[:6]}"
    assert result.report.counters["footnotes"] == sum(
        1 for page in expected_pages if any(p.startswith("Nota ") for p in page)
    )


def test_reading_order_gate_sees_a_scrambled_column(tmp_path, monkeypatch):
    """Vitality: reading the right column first must fail the gate."""
    from caissa.ocr.layout import analyze

    real = analyze.reading_order

    def scrambled(lines, indices, page_box, config=None):
        order = real(lines, indices, page_box, config)
        return list(reversed(order))

    monkeypatch.setattr(analyze, "reading_order", scrambled)
    blob, expected_pages = _two_column_book(seed=7, pages=6)
    path = tmp_path / "colunas-sabotadas.pdf"
    path.write_bytes(blob)
    result = import_pdf(path, PdfImportOptions(detect_diagrams=False))
    correct, total, _ = _order_score(result.document, expected_pages)
    assert correct < total, "a sabotagem da ordem de leitura passou pelo portão"
