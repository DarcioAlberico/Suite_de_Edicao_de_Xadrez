"""«Medir no livro»: the labelled lines read again, scored per partition, with
unread lines counted against the reader and blind lines left out."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from caissa.ocr.golden import Partition, partition_for
from caissa.ocr.labeling import (
    LabelProject,
    LineLabel,
    LineStatus,
    PageLabels,
    RegionLabel,
    item_id_for,
)
from caissa.ocr.labeling.measure import BookMeasure, MeasureGroup, SideMeasure, score_lines

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _line(index: int, y: float, hypothesis: str, truth: str = "", *, status=LineStatus.ACCEPTED):
    return LineLabel(
        index=index,
        box=(50, y, 300, y + 10),
        hypothesis=hypothesis,
        confidence=0.9,
        truth=truth,
        status=status,
    )


def _page(document: str, page_index: int, lines: list[LineLabel]) -> PageLabels:
    region = RegionLabel(
        index=0,
        rect=(50, 100, 300, 160),
        kind="movetext",
        reading_order=0,
        lines=lines,
    )
    return PageLabels(
        document=document,
        pdf_path="",
        page_index=page_index,
        width_pt=400,
        height_pt=600,
        dpi=300,
        lang="eng",
        regions=[region],
    )


def _page_index(document: str, partition: Partition, rect=(50, 100, 300, 160)) -> int:
    return next(
        i for i in range(1000) if partition_for(item_id_for(document, i, rect)) is partition
    )


def _recognised(document: str, page_index: int, texts: dict[float, str]) -> PageLabels:
    """A fresh recognition: one line per ``y`` with the engine's text."""
    return _page(
        document,
        page_index,
        [_line(n, y, text, status=LineStatus.PENDING) for n, (y, text) in enumerate(texts.items())],
    )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def test_group_counts_cer_moves_figurines_and_unread():
    group = MeasureGroup()
    group.add("36... ♖e8! ♗h6", "36... ♖e8! ♗h6")
    group.add("37 ♘f3", "37 Sf3")
    group.add("prose line", None)
    assert group.lines == 3
    assert group.unread == 1
    assert group.exact == 1
    assert group.moves_truth == 3
    assert group.moves_kept == 2
    assert group.moves_invented == 1, "Sf3 is a move the truth does not have"
    assert group.figurines_truth == 3
    assert group.figurines_kept == 2
    assert group.figurines_invented == 0
    assert group.by_piece == {"♖": [1, 1], "♗": [1, 1], "♘": [1, 0]}
    assert group.piece_rate("♘") == 0
    assert group.piece_rate("♕") == 1.0, "a piece the truth never had is not a miss"
    assert group.rarest_piece() == "♖", "ties go to the first piece in ♔♕♖♗♘♙ order"
    # The unread line costs every one of its characters.
    assert group.edits == 1 + len("prose line")
    assert group.cer == pytest.approx(group.edits / group.truth_chars)
    group.add("prose", "♔ prose ♕")
    assert group.figurines_invented == 2, "figurines the truth does not have are invented"


def test_score_lines_matches_by_overlap_and_groups_by_partition():
    document = "Livro"
    dev = _page_index(document, Partition.DEV)
    labelled = _page(
        document,
        dev,
        [
            _line(0, 100, "36... Hea!", "36... ♖e8!", status=LineStatus.EDITED),
            _line(1, 115, "White has", "White has"),
            _line(2, 130, "noise", status=LineStatus.REJECTED),
            _line(3, 145, "pending", status=LineStatus.PENDING),
        ],
    )
    side = SideMeasure(label="com modelo")
    # The first strip moved a little (still overlapping); the second is gone.
    recognised = _recognised(document, dev, {102: "36... ♖e8!", 400: "White has"})
    assert score_lines(labelled, recognised, side) == 2, "rejected and pending lines are not truth"
    group = side.groups[str(Partition.DEV)]
    assert group.lines == 2
    assert group.exact == 1
    assert group.unread == 1
    assert group.figurines_kept == 1
    assert side.groups["total"].lines == 2


def test_blind_regions_never_enter_the_measure():
    document = "Livro"
    blind = _page_index(document, Partition.BLIND)
    labelled = _page(document, blind, [_line(0, 100, "1.e4 e5", "1.e4 e5")])
    side = SideMeasure(label="x")
    assert score_lines(labelled, _recognised(document, blind, {100: "1.e4 e5"}), side) == 0
    assert side.groups == {}


def test_markdown_puts_the_held_out_lines_first_and_saves(tmp_path: Path):
    without, with_model = SideMeasure(label="sem modelo"), SideMeasure(label="com modelo")
    without.add("calib", "36... ♖e8!", "36... Hea!")
    with_model.add("calib", "36... ♖e8!", "36... ♖e8!")
    without.add("dev", "1.e4 e5", "1.e4 e5")
    with_model.add("dev", "1.e4 e5", "1.e4 e5")
    measure = BookMeasure(
        document="Livro", pages=[3, 4], sides=[without, with_model], lines_blind=2
    )
    text = measure.markdown()
    calib_row = text.index("avaliação (`calib`, fora do treino)")
    dev_row = text.index("treino (`dev`)")
    assert calib_row < dev_row < text.index("| todas")
    assert "| figurinas certas | 0 / 1 | 1 / 1 |" in text
    assert "2 linhas cegas fora da conta" in text
    json_path, md_path = measure.save(tmp_path / "medidas")
    assert json_path.name == "livro.json" and md_path.read_text("utf-8") == text
    assert '"figurines_kept": 1' in json_path.read_text("utf-8")


# --------------------------------------------------------------------------- #
# End to end over a PDF, with a fake service
# --------------------------------------------------------------------------- #


@dataclass
class _Word:
    text: str
    confidence: float
    box: object
    word_index: int = 0


@dataclass
class _Line:
    words: tuple
    box: object
    block_index: int = 0
    paragraph_index: int = 0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def confidence(self) -> float:
        return min(w.confidence for w in self.words)


@dataclass
class _Result:
    lines: tuple


@dataclass
class _Region:
    reading_order: int
    kind: str
    box_px: object
    result: _Result
    decision: object
    engine: str = "tesseract"
    variant: str = "original"
    score: float = 0.7
    candidates: tuple = ()


@dataclass
class _Recognition:
    dpi: float
    regions: list
    engines: dict = field(default_factory=lambda: {"tesseract": "5.5"})
    notes: list = field(default_factory=list)


class _Reader:
    """Answers one movetext line at a fixed place with the text it is given."""

    lang = "eng"

    def __init__(self, text: str) -> None:
        self.text = text

    def recognize_image(self, image, *, dpi, lang="", page_index=0):
        from caissa.ocr.types import BBox

        scale = dpi / 72.0
        words = tuple(
            _Word(tok, 0.9, BBox((50 + 40 * n) * scale, 100 * scale, 35 * scale, 10 * scale), n)
            for n, tok in enumerate(self.text.split())
        )
        line = _Line(words, BBox(50 * scale, 100 * scale, 250 * scale, 10 * scale))
        decision = SimpleNamespace(decision="accepted", reasons_pt=())
        region = _Region(0, "movetext", BBox(50 * scale, 100 * scale, 250 * scale, 60 * scale),
                         _Result((line,)), decision)
        return _Recognition(dpi=dpi, regions=[region])


def test_measure_book_reads_every_labelled_page_with_each_service(tmp_path: Path):
    pymupdf = pytest.importorskip("pymupdf")
    from caissa.ocr.labeling.measure import measure_book

    pdf = tmp_path / "Livro.pdf"
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page(width=400, height=600)
    doc.save(pdf)
    doc.close()
    project = LabelProject.open_or_create(tmp_path / "proj", reviewer="ana")
    project.add_document(pdf)
    index = _page_index("Livro", Partition.DEV, rect=(50, 100, 250, 110))
    page = PageLabels(
        document="Livro",
        pdf_path=str(pdf),
        page_index=index,
        width_pt=400,
        height_pt=600,
        dpi=150,
        lang="eng",
        regions=[
            RegionLabel(
                index=0,
                rect=(50, 100, 250, 110),
                kind="movetext",
                reading_order=0,
                lines=[
                    LineLabel(
                        index=0,
                        box=(50, 100, 250, 110),
                        hypothesis="36... Hea!",
                        truth="36... ♖e8!",
                        status=LineStatus.EDITED,
                    )
                ],
            )
        ],
    )
    project.pages[page.key] = page
    seen: list[str] = []
    measure = measure_book(
        project,
        "Livro",
        {"sem modelo": _Reader("36... Hea!"), "com modelo": _Reader("36... ♖e8!")},
        progress=seen.append,
    )
    assert measure.notes == []
    assert measure.pages == [index]
    assert seen == [f"página {index} · sem modelo", f"página {index} · com modelo"]
    before, after = measure.sides
    assert before.groups["total"].figurines_kept == 0
    assert after.groups["total"].figurines_kept == 1
    assert after.groups["total"].exact == 1
    assert before.groups["total"].moves_kept == 0 and after.groups["total"].moves_kept == 1
