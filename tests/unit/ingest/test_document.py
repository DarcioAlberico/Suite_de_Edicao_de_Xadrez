"""One open PDF: validation, metadata, outline, pages, lock."""

from __future__ import annotations

import threading

import pytest

from caissa.ingest.pdf.document import (
    PdfDocument,
    PdfMetadata,
    PdfOpenError,
    clean_metadata_text,
    open_count,
    open_pdf,
    sample_indices,
)

from .conftest import PageSpec, build_pdf, requires_pymupdf

pytestmark = requires_pymupdf


# --------------------------------------------------------------------------- #
# Opening
# --------------------------------------------------------------------------- #


def test_open_counts_pages_without_touching_them(pdf_file):
    path = pdf_file([PageSpec().text("um", 72, 100), PageSpec().text("dois", 72, 100)])
    before = open_count()
    with open_pdf(path) as doc:
        assert doc.page_count == 2
        assert len(doc) == 2
        assert doc.is_owned
        assert doc.source_name == path.name
    assert open_count() == before + 1
    assert doc.is_closed


def test_open_from_bytes():
    blob = build_pdf([PageSpec().text("memória", 72, 100)])
    with open_pdf(blob) as doc:
        assert doc.page_count == 1
        assert doc.path is None
        assert doc.content_hash is None


def test_missing_file_is_refused_in_portuguese(tmp_path):
    with pytest.raises(PdfOpenError, match="não existe"):
        open_pdf(tmp_path / "nada.pdf")


def test_a_non_pdf_is_refused(tmp_path):
    """MuPDF happily opens XPS, CBZ, SVG and plain text as one-page books."""
    target = tmp_path / "nota.txt"
    target.write_text("isto não é um PDF\n" * 20, encoding="utf-8")
    with pytest.raises(PdfOpenError, match="não é um PDF"):
        open_pdf(target)


def test_an_encrypted_pdf_is_refused_at_open(tmp_path):
    """``needs_pass`` is set, ``page_count`` answers, and only a page access
    would raise -- in English, three layers away.  The refusal is here."""
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "segredo")
    target = tmp_path / "senha.pdf"
    doc.save(
        str(target),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="dono",
        user_pw="leitor",
    )
    doc.close()
    with pytest.raises(PdfOpenError, match="protegido por senha"):
        open_pdf(target)


def test_borrowed_document_is_never_closed_by_the_borrower(pdf_file):
    import pymupdf

    path = pdf_file([PageSpec().text("emprestado", 72, 100)])
    raw = pymupdf.open(str(path))
    borrowed = PdfDocument.borrow(raw)
    assert not borrowed.is_owned
    assert borrowed.page_count == 1
    borrowed.close()
    assert not raw.is_closed, "fechar o emprestado não pode fechar o documento do dono"
    raw.close()


def test_borrow_validates_too(tmp_path):
    import pymupdf

    target = tmp_path / "nota.txt"
    target.write_text("texto\n" * 10, encoding="utf-8")
    raw = pymupdf.open(str(target))
    with pytest.raises(PdfOpenError, match="não é um PDF"):
        PdfDocument.borrow(raw)
    raw.close()


# --------------------------------------------------------------------------- #
# Pages and frames
# --------------------------------------------------------------------------- #


def test_page_index_is_validated_in_portuguese(pdf_file):
    path = pdf_file([PageSpec().text("uma", 72, 100)])
    with open_pdf(path) as doc, pytest.raises(IndexError, match="fora do intervalo"):
        doc.page(3)


def test_frame_is_captured_once_and_cached(pdf_file):
    path = pdf_file([PageSpec(size=(400.0, 600.0), rotation=90).text("x", 72, 100)])
    with open_pdf(path) as doc:
        first = doc.frame(0)
        assert first is doc.frame(0)
        assert (first.width, first.height) == (600.0, 400.0)
        assert first.rotation == 90


def test_pages_iterates_one_at_a_time(pdf_file):
    path = pdf_file([PageSpec().text(f"p{i}", 72, 100) for i in range(5)])
    with open_pdf(path) as doc:
        seen = [(i, page.get_text().strip()) for i, page in doc.pages([4, 1])]
    assert seen == [(4, "p4"), (1, "p1")]


def test_lock_serialises_concurrent_readers(pdf_file):
    """PyMuPDF is not thread-safe; the lock is what keeps two readers apart."""
    path = pdf_file([PageSpec().text(f"página {i}", 72, 100) for i in range(8)])
    errors: list[BaseException] = []

    with open_pdf(path) as doc:

        def worker() -> None:
            try:
                for _ in range(20):
                    for index in range(doc.page_count):
                        with doc.locked() as raw:
                            assert raw[index].get_text().strip() == f"página {index}"
            except BaseException as exc:  # noqa: BLE001 - collected for the assertion
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert not errors


# --------------------------------------------------------------------------- #
# Metadata and outline
# --------------------------------------------------------------------------- #


def test_metadata_is_read_and_cleaned(tmp_path):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "x")
    doc.set_metadata(
        {"title": "📚 Chess Structures ", "author": "unknown", "subject": " a\u200bb "}
    )
    target = tmp_path / "meta.pdf"
    doc.save(str(target))
    doc.close()
    with open_pdf(target) as opened:
        meta = opened.metadata
    assert meta.title == "Chess Structures"
    assert meta.author == ""
    assert meta.subject == "ab"  # the zero-width space (Cf) is dropped
    assert not meta.title_from_filename


def test_title_falls_back_to_the_file_name(pdf_file):
    path = pdf_file([PageSpec().text("x", 72, 100)], name="Dvoretsky - Endgame Manual (2025).pdf")
    with open_pdf(path) as doc:
        meta = doc.metadata
    assert meta.title_from_filename
    assert meta.title == "Endgame Manual (2025)"
    assert meta.author == "Dvoretsky"


@pytest.mark.parametrize(
    ("raw", "title", "author"),
    [
        ({"title": "Chess Structures - Flores Rios"}, "Chess Structures", "Flores Rios"),
        ({"title": "A - B - C", "author": "X"}, "A - B - C", "X"),
    ],
)
def test_calibre_packs_author_into_the_title_field(raw, title, author):
    meta = PdfMetadata.from_raw(raw, None)
    assert (meta.title, meta.author) == (title, author)


def test_file_name_head_that_is_not_an_author_stays_in_the_title():
    from pathlib import Path

    meta = PdfMetadata.from_raw({}, Path("1000 Chess Problems - Yakov Vladimirov 2015.pdf"))
    assert meta.title == "1000 Chess Problems - Yakov Vladimirov 2015"
    assert meta.author == ""


def test_clean_metadata_text_keeps_astral_letters_and_drops_pictographs():
    assert clean_metadata_text("📚 Título 𝔘nicode") == "Título 𝔘nicode"
    assert clean_metadata_text(None) == ""


def test_outline_is_zero_based_and_clamped(pdf_file):
    path = pdf_file(
        [PageSpec().text(f"p{i}", 72, 100) for i in range(3)],
        toc=[(1, "Capítulo 1", 0), (2, "Seção 1.1", 1), (1, "Capítulo 2", 2)],
    )
    with open_pdf(path) as doc:
        outline = doc.outline
    assert [(e.level, e.title, e.page_index) for e in outline] == [
        (1, "Capítulo 1", 0),
        (2, "Seção 1.1", 1),
        (1, "Capítulo 2", 2),
    ]


def test_content_hash_is_lazy_and_stable(pdf_file):
    import hashlib

    path = pdf_file([PageSpec().text("x", 72, 100)])
    with open_pdf(path) as doc:
        assert doc.content_hash == hashlib.sha256(path.read_bytes()).hexdigest()
        assert doc.content_hash is doc.content_hash


# --------------------------------------------------------------------------- #
# Sampling
# --------------------------------------------------------------------------- #


def test_sample_indices_avoid_both_covers():
    indices = sample_indices(100, 5)
    assert indices == sorted(set(indices))
    assert 0 not in indices
    assert 99 not in indices
    assert len(indices) == 5


def test_sample_indices_degenerate_cases():
    assert sample_indices(0, 5) == []
    assert sample_indices(3, 0) == []
    assert sample_indices(3, 10) == [0, 1, 2]
