"""OCR_UI_ROADMAP_C2 passo B9: cancellation inside the page, parallel readings.

Before: the importer looked at its hook between pages, and a Tesseract
child ran its 180 s to the end.  Now the hook travels as a context variable
into every engine call and every worker thread; the Tesseract runner polls
it and kills the child; the service runs a region's independent readings
on a pool and keeps their order, so a page reads the same on one thread or
four.
"""

from __future__ import annotations

import sys
import threading
import time

import numpy as np
import pytest

from caissa.ingest.pdf.ocr_service import OcrService, OcrServiceConfig
from caissa.ocr.cancel import OcrCanceled, cancellable, check_cancel, should_cancel
from caissa.ocr.engines.tesseract import TesseractConfig, TesseractEngine

# --------------------------------------------------------------------------- #
# The hook
# --------------------------------------------------------------------------- #


def test_the_hook_is_scoped_to_the_context():
    assert not should_cancel()
    with cancellable(lambda: True):
        assert should_cancel()
        with pytest.raises(OcrCanceled):
            check_cancel()
    assert not should_cancel()
    check_cancel()


def test_a_worker_thread_only_sees_the_hook_when_given_the_context():
    import contextvars

    seen: dict[str, bool] = {}
    with cancellable(lambda: True):
        context = contextvars.copy_context()
        plain = threading.Thread(target=lambda: seen.__setitem__("plain", should_cancel()))
        copied = threading.Thread(target=context.run,
                                  args=(lambda: seen.__setitem__("copied", should_cancel()),))
        plain.start(); copied.start(); plain.join(); copied.join()
    assert seen == {"plain": False, "copied": True}


def test_cancellation_is_not_an_exception_a_candidate_guard_swallows():
    """Every ``except Exception`` on the OCR path must let it through."""
    assert not issubclass(OcrCanceled, Exception)
    assert issubclass(OcrCanceled, BaseException)


# --------------------------------------------------------------------------- #
# The Tesseract runner
# --------------------------------------------------------------------------- #


def test_the_runner_kills_the_child_when_the_hook_says_stop():
    engine = TesseractEngine(TesseractConfig(cancel_poll_s=0.05))
    sleeper = [sys.executable, "-c", "import time; time.sleep(30)"]
    started = time.perf_counter()
    with cancellable(lambda: True), pytest.raises(OcrCanceled):
        engine._run(sleeper, timeout=60.0)
    assert time.perf_counter() - started < 5.0


def test_the_runner_still_times_out_without_a_hook():
    engine = TesseractEngine(TesseractConfig(cancel_poll_s=0.05))
    sleeper = [sys.executable, "-c", "import time; time.sleep(30)"]
    from caissa.ocr.engines.base import OcrError

    started = time.perf_counter()
    with pytest.raises(OcrError, match="tempo limite"):
        engine._run(sleeper, timeout=0.3)
    assert time.perf_counter() - started < 5.0


def test_the_runner_returns_the_childs_output_when_it_finishes():
    engine = TesseractEngine(TesseractConfig())
    proc = engine._run([sys.executable, "-c", "print('ola')"], timeout=30.0)
    assert proc.returncode == 0 and proc.stdout.strip() == "ola"


def test_the_child_gets_one_openmp_thread_by_default():
    assert TesseractEngine(TesseractConfig())._child_env()["OMP_THREAD_LIMIT"] == "1"
    assert TesseractEngine(TesseractConfig(omp_thread_limit=None))._child_env() is None


# --------------------------------------------------------------------------- #
# The service's pool
# --------------------------------------------------------------------------- #


def test_readings_come_back_in_submission_order_whatever_the_threads_did():
    service = OcrService([], OcrServiceConfig(workers=4), lang="eng")
    delays = [0.15, 0.0, 0.1, 0.05]

    def reading(n: int, delay: float):
        def run():
            time.sleep(delay)
            return [n]
        return run

    out = service._run_readings([reading(n, d) for n, d in enumerate(delays)])
    assert out == [[0], [1], [2], [3]]


def test_one_worker_is_the_serial_loop():
    service = OcrService([], OcrServiceConfig(workers=1), lang="eng")
    calls: list[int] = []

    def reading(n: int):
        def run():
            calls.append(n)
            return [n]
        return run

    assert service._run_readings([reading(n) for n in range(3)]) == [[0], [1], [2]]
    assert calls == [0, 1, 2]
    assert service._pool is None


def test_a_cancellation_in_a_worker_reaches_the_caller_after_the_others_finish():
    service = OcrService([], OcrServiceConfig(workers=4), lang="eng")
    finished: list[int] = []

    def fine(n: int):
        def run():
            time.sleep(0.05)
            finished.append(n)
            return [n]
        return run

    def cancels():
        raise OcrCanceled("stop")

    with pytest.raises(OcrCanceled):
        service._run_readings([fine(0), cancels, fine(2)])
    assert sorted(finished) == [0, 2]


def test_the_hook_reaches_the_workers():
    service = OcrService([], OcrServiceConfig(workers=2), lang="eng")

    def probe():
        return [should_cancel()]

    with cancellable(lambda: True):
        assert service._run_readings([probe, probe]) == [[True], [True]]
    assert service._run_readings([probe, probe]) == [[False], [False]]


# --------------------------------------------------------------------------- #
# The importer turns it into its own cancellation
# --------------------------------------------------------------------------- #


def test_an_ocr_canceled_inside_a_page_becomes_an_import_canceled(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    from caissa.ingest.pdf.importer import ImportCanceled, PdfImportOptions, import_pdf

    doc = pymupdf.open()
    for _ in range(3):
        page = doc.new_page(width=300, height=300)
        page.insert_image(page.rect, pixmap=pymupdf.Pixmap(pymupdf.csGRAY, (0, 0, 60, 60), 0))
    path = tmp_path / "scan.pdf"
    doc.save(path); doc.close()

    def provider(page, frame, verdict):
        if frame.index == 1:
            raise OcrCanceled("stop inside the page")
        return None

    options = PdfImportOptions(ocr=provider, detect_diagrams=False)
    with pytest.raises(ImportCanceled, match="durante o OCR"):
        import_pdf(path, options)
    kept = import_pdf(path, PdfImportOptions(ocr=provider, detect_diagrams=False,
                                             keep_partial=True))
    assert kept.report.canceled
    assert len(kept.report.pages) == 1
