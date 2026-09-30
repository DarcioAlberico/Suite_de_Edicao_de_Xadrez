"""OCR_UI ciclo 2, passo A2: the product's import finds raster diagrams by default.

``docs/OCR_UI_ANALISE_C2.md`` §3.2: nothing in the product passed
``diagram_finder``, so a raster book (the Aagaard) came out of the window's
import with 0 diagrams and "nada para rever".  Pinned here, without a model:

* ``PdfImportOptions()`` resolves to :func:`~caissa.ingest.pdf.finders.combined_finder`;
  ``detect_raster_diagrams=False`` is the vector route alone and
  ``detect_diagrams=False`` is none -- the sabotage of the roadmap, at the option;
* the classifier is one per process: the three finders of a ``combined_finder``
  share it through the residency manager (``shared_square_classifier``), and a
  second book does not load it again.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from caissa.ingest.pdf import PdfImportOptions, finders
from caissa.ingest.pdf.importer import PdfImporter, vector_diagram_finder
from caissa.vision.classify import residency


class _Document:
    """The two attributes ``PdfImporter.__init__`` reads from a ``PdfDocument``."""

    page_count = 1
    path = None
    content_hash = "0" * 64
    outline = ()

    def frame(self, index: int):
        raise AssertionError("the finder is resolved without touching a page")


def _importer(**options) -> PdfImporter:
    return PdfImporter(_Document(), PdfImportOptions(**options))  # type: ignore[arg-type]


def test_the_default_finder_is_every_route(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(finders, "combined_finder", lambda **_kw: sentinel)
    assert _importer()._finder() is sentinel


def test_the_option_falls_back_to_the_vector_route_or_to_nothing(monkeypatch) -> None:
    monkeypatch.setattr(finders, "combined_finder", lambda **_kw: pytest.fail("não devia montar"))
    assert _importer(detect_raster_diagrams=False)._finder() is vector_diagram_finder
    assert _importer(detect_diagrams=False)._finder() is None
    assert _importer(detect_diagrams=False, detect_raster_diagrams=True)._finder() is None


def test_a_finder_given_by_the_caller_wins(monkeypatch) -> None:
    monkeypatch.setattr(finders, "combined_finder", lambda **_kw: pytest.fail("não devia montar"))
    def mine(_page, _frame, _text):
        return []

    assert _importer(diagram_finder=mine)._finder() is mine
    assert _importer(diagram_finder=mine, detect_diagrams=False)._finder() is mine


def test_the_classifier_is_loaded_once_per_process_and_shared(monkeypatch) -> None:
    loads: list[str] = []

    class _Manager:
        def __init__(self) -> None:
            self._specs: dict[str, object] = {}

        def registered(self) -> tuple[str, ...]:
            return tuple(self._specs)

        def register(self, spec, *, replace=False) -> None:
            self._specs[spec.name] = spec

        class _Lease:
            def __init__(self, model) -> None:
                self.model = model

        def acquire(self, name: str):
            import contextlib

            spec = self._specs[name]
            loads.append(name)
            model = spec.loader("cpu")

            @contextlib.contextmanager
            def lease():
                yield self._Lease(model)

            return lease()

    manager = _Manager()
    monkeypatch.setattr(residency, "_shared", None)
    monkeypatch.setattr(
        "caissa.vision.runtime.get_residency_manager", lambda: manager, raising=False
    )
    fake = SimpleNamespace(model_hash="deadbeef")
    monkeypatch.setattr(
        residency, "register_square_classifier",
        lambda m=None, **kw: m.register(SimpleNamespace(name=residency.SQUARE_CLASSIFIER,
                                                         loader=lambda device: fake)),
    )
    first = residency.shared_square_classifier(manager)
    second = residency.shared_square_classifier(manager)
    assert first is fake
    assert second is fake
    assert loads == [residency.SQUARE_CLASSIFIER], "uma carga por processo, e só uma"
    # The finders ask the same place, so a combined finder's three routes share it.
    monkeypatch.setattr(residency, "shared_square_classifier", lambda *a, **k: fake)
    assert finders.shared_classifier() is fake
    assert finders._model_hash(fake) == "deadbeef"


def test_without_any_classifier_the_finder_locates_and_says_so(monkeypatch, caplog) -> None:
    def refuse(*_a, **_k):
        raise RuntimeError("sem pesos")

    monkeypatch.setattr(residency, "shared_square_classifier", refuse)
    monkeypatch.setattr("caissa.vision.classify.batched.load_classifier", refuse)
    with caplog.at_level("WARNING", logger="caissa.ingest.pdf.finders"):
        assert finders.shared_classifier() is None
    assert any("Classificador indisponível" in r.getMessage() for r in caplog.records)
