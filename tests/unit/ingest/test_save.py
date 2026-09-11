"""Atomic, cancelable PDF writing."""

from __future__ import annotations

import pytest

from caissa.ingest.pdf.save import EXPORT_PART_SUFFIX, ExportCanceled, save_document_atomically

from .conftest import PageSpec, build_pdf, requires_pymupdf

pytestmark = requires_pymupdf


def _doc(pages: int = 3):
    import pymupdf

    return pymupdf.open(
        "pdf", build_pdf([PageSpec().text(f"página {i}", 72, 100) for i in range(pages)])
    )


def test_save_writes_a_whole_file_and_no_partial(tmp_path):
    target = tmp_path / "saida.pdf"
    doc = _doc()
    save_document_atomically(doc, target)
    doc.close()
    assert target.is_file()
    assert not target.with_name(target.name + EXPORT_PART_SUFFIX).exists()
    import pymupdf

    with pymupdf.open(str(target)) as reopened:
        assert reopened.page_count == 3


def test_cancel_during_writing_leaves_the_previous_file_untouched(tmp_path):
    target = tmp_path / "saida.pdf"
    target.write_bytes(b"conteudo anterior")
    doc = _doc(pages=40)
    calls = {"n": 0}

    def should_cancel() -> bool:
        calls["n"] += 1
        return calls["n"] > 1  # let the first check pass, stop on the next

    with pytest.raises(ExportCanceled):
        save_document_atomically(doc, target, should_cancel=should_cancel)
    doc.close()
    assert target.read_bytes() == b"conteudo anterior"
    assert not target.with_name(target.name + EXPORT_PART_SUFFIX).exists()


def test_cancel_before_publishing_is_honoured(tmp_path):
    target = tmp_path / "saida.pdf"
    doc = _doc(pages=1)
    with pytest.raises(ExportCanceled, match="antes de publicar"):
        # The writer never asks (too few writes); the final check does.
        save_document_atomically(doc, target, should_cancel=lambda: True)
    doc.close()
    assert not target.exists()


def test_a_stale_partial_is_removed_first(tmp_path):
    target = tmp_path / "saida.pdf"
    stale = target.with_name(target.name + EXPORT_PART_SUFFIX)
    stale.write_bytes(b"lixo de uma exportacao morta")
    doc = _doc()
    save_document_atomically(doc, target)
    doc.close()
    assert target.is_file()
    assert not stale.exists()


def test_an_error_while_writing_cleans_up(tmp_path):
    target = tmp_path / "saida.pdf"

    class Broken:
        def save(self, *_args, **_kwargs):
            raise RuntimeError("falha simulada")

    with pytest.raises(RuntimeError, match="falha simulada"):
        save_document_atomically(Broken(), target)
    assert not target.exists()
    assert not target.with_name(target.name + EXPORT_PART_SUFFIX).exists()
