"""Sol §SOL-0/§SOL-11: a labelling project records every verdict, exports
to the three consumers in their shapes, and never lets a blind page out as
training or calibration data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from caissa.ocr.golden import Partition, load_manifest, partition_for
from caissa.ocr.labeling import (
    LabelProject,
    LineLabel,
    LineStatus,
    PageLabels,
    RegionLabel,
    WordHint,
    item_id_for,
)
from caissa.ocr.labeling.export import (
    calibration_pairs,
    corrections,
    manifest_items,
    merge_into_manifest,
    normalise_truth,
    partition_split,
    write_ground_truth,
)
from caissa.ocr.review import blind_guard

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _line(index: int, y: float, text: str, conf: float = 0.95, *, alt: tuple = ()) -> LineLabel:
    words = tuple(
        WordHint(text=w, confidence=conf if n else 0.99, box=(50 + 30 * n, y, 78 + 30 * n, y + 10))
        for n, w in enumerate(text.split())
    )
    return LineLabel(
        index=index,
        box=(50, y, 300, y + 10),
        hypothesis=text,
        confidence=conf,
        words=words,
        alternatives=alt,
    )


def _page(document: str = "Livro", page_index: int = 3, *, pdf_path: str = "") -> PageLabels:
    region = RegionLabel(
        index=0,
        rect=(50, 100, 300, 150),
        kind="paragraph",
        reading_order=0,
        engine="tesseract",
        score=0.8,
        decision="review",
        prose_lang="pt",
        notation_lang="pt",
        lines=[
            _line(0, 100, "1.e4 e5 2.Cf3 Cc6 3.Bb5 a6 4.Ba4 Cf6"),
            _line(
                1,
                115,
                "a torre pertence à coluna aberta",
                conf=0.6,
                alt=(("upscale/tesseract", "a torre pertence a coluna aberta"),),
            ),
            _line(2, 130, "ruído", conf=0.2),
        ],
    )
    return PageLabels(
        document=document,
        pdf_path=pdf_path,
        page_index=page_index,
        width_pt=400,
        height_pt=600,
        dpi=300,
        lang="por+eng",
        regions=[region],
    )


def _blind_page_index(document: str, rect=(50, 100, 300, 150)) -> tuple[int, int]:
    """A page index whose region id hashes to blind, and one that does not."""
    blind = next(
        i for i in range(1000) if partition_for(item_id_for(document, i, rect)) is Partition.BLIND
    )
    open_ = next(
        i
        for i in range(1000)
        if partition_for(item_id_for(document, i, rect)) is not Partition.BLIND
    )
    return blind, open_


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #


def test_decisions_are_recorded_timed_and_audited(tmp_path: Path):
    project = LabelProject.open_or_create(tmp_path / "proj", reviewer="ana")
    page = _page()
    project.put_page(page)
    l0, l1, l2 = page.regions[0].lines
    project.decide(page, l0, LineStatus.ACCEPTED, seconds=2.5)
    project.decide(
        page, l1, LineStatus.EDITED, text="a torre pertence à coluna aberta.", seconds=8.0
    )
    project.decide(page, l2, LineStatus.REJECTED, seconds=1.0, note="mancha")
    assert l0.text == l0.hypothesis
    assert l1.text.endswith(".")
    assert l2.text == ""
    assert l0.reviewer == "ana"
    assert page.seconds == pytest.approx(11.5)
    assert page.regions[0].complete
    audit = [
        json.loads(row)
        for row in (tmp_path / "proj" / "audit.jsonl").read_text("utf-8").splitlines()
    ]
    assert [a["action"] for a in audit] == ["accepted", "edited", "rejected"]
    with pytest.raises(ValueError, match="texto corrigido"):
        project.decide(page, l0, LineStatus.EDITED)


def test_project_round_trips_through_disk(tmp_path: Path):
    project = LabelProject.open_or_create(tmp_path / "proj", name="p", reviewer="ana")
    project.add_document(tmp_path / "Livro.pdf")
    page = _page()
    project.put_page(page)
    project.decide(page, page.regions[0].lines[1], LineStatus.EDITED, text="corrigida")
    project.save()
    again = LabelProject.load(tmp_path / "proj")
    assert again.reviewer == "ana"
    assert "Livro" in again.documents
    loaded = again.page("Livro", 3)
    assert loaded is not None
    line = loaded.regions[0].lines[1]
    assert line.status is LineStatus.EDITED
    assert line.truth == "corrigida"
    assert line.alternatives == (("upscale/tesseract", "a torre pertence a coluna aberta"),)
    assert loaded.regions[0].lines[0].words[1].confidence == pytest.approx(0.95)
    assert again.summary()["lines"]["edited"] == 1


def test_doubt_follows_weak_words_empty_readings_and_disagreement():
    page = _page()
    l0, l1, l2 = page.regions[0].lines
    assert not l0.doubtful(0.85)
    assert l1.doubtful(0.85)
    assert l1.low_confidence_words(0.85)
    assert l2.doubtful(0.85)
    assert LineLabel(index=9, box=(0, 0, 1, 1), hypothesis="").doubtful(0.85)
    sure = _line(3, 0, "texto", conf=0.99, alt=(("x", "outro"),))
    assert sure.doubtful(0.85), "a candidate that disagrees is a doubt even at high confidence"


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #


def _decided_project(
    tmp_path: Path, page_index: int, *, document: str = "Livro"
) -> tuple[LabelProject, PageLabels]:
    project = LabelProject.open_or_create(tmp_path / "proj", name="p", reviewer="ana")
    page = _page(document, page_index)
    project.put_page(page)
    l0, l1, l2 = page.regions[0].lines
    project.decide(page, l0, LineStatus.ACCEPTED)
    project.decide(page, l1, LineStatus.EDITED, text="a torre pertence à coluna aberta.")
    project.decide(page, l2, LineStatus.REJECTED)
    return project, page


def test_manifest_items_carry_the_human_truth_and_the_scan_source(tmp_path: Path):
    _, open_index = _blind_page_index("Livro")
    project, page = _decided_project(tmp_path, open_index)
    page.regions[0].start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    items = manifest_items(project)
    assert len(items) == 1
    item = items[0]
    assert item.regions[0].start_fen.startswith("rnbqkbnr/")
    assert str(item.source) == "pdf-scan"
    assert item.book == "Livro"
    assert item.page_index == open_index
    assert item.clip == (50.0, 100.0, 300.0, 150.0)
    assert (
        item.regions[0].truth
        == "1.e4 e5 2.Cf3 Cc6 3.Bb5 a6 4.Ba4 Cf6\na torre pertence à coluna aberta."
    )
    assert item.genre == "movetext"
    assert item.regions[0].kind == "movetext"
    assert item.regions[0].moves[:3] == ("e4", "e5", "Cf3")
    assert "human-labelled" in item.tags
    assert item.strata == ("native",)
    # Incomplete region: nothing exported.
    project.reset(page, page.regions[0].lines[0])
    assert manifest_items(project) == []


def test_merge_into_manifest_replaces_by_id_and_keeps_blind(tmp_path: Path):
    blind_index, open_index = _blind_page_index("Livro")
    project, _ = _decided_project(tmp_path, open_index)
    blind_page = _page("Livro", blind_index)
    project.put_page(blind_page)
    for line in blind_page.regions[0].lines:
        project.decide(blind_page, line, LineStatus.ACCEPTED)
    manifest = tmp_path / "manifest.json"
    added, replaced = merge_into_manifest(manifest, manifest_items(project))
    assert (added, replaced) == (2, 0)
    added, replaced = merge_into_manifest(manifest, manifest_items(project))
    assert (added, replaced) == (0, 2)
    assert len(load_manifest(manifest, include_blind=True)) == 2
    assert len(load_manifest(manifest)) == 1, "the blind item is hidden by default"


def test_corrections_and_pairs_withhold_blind_pages(tmp_path: Path):
    blind_index, open_index = _blind_page_index("Livro")
    project, _ = _decided_project(tmp_path, open_index)
    blind_page = _page("Livro", blind_index)
    project.put_page(blind_page)
    for line in blind_page.regions[0].lines:
        project.decide(blind_page, line, LineStatus.ACCEPTED)
    rows = corrections(project)
    assert {r["page_index"] for r in rows} == {open_index}
    assert sorted(r["action"] for r in rows) == ["accept", "edit"]
    pairs = calibration_pairs(project)
    assert all(p["engine"] == "tesseract" for p in pairs)
    assert len(pairs) == 2
    edited = next(p for p in pairs if len(p["pairs"]) == 6)
    assert [ok for _, ok in edited["pairs"]] == [True] * 5 + [False], "the last word changed"
    assert project.blind_regions() == 1
    # The review model's guard agrees on which page is blind.
    guard = blind_guard(i.id for i in manifest_items(project))
    assert guard("Livro", blind_index)
    assert not guard("Livro", open_index)


def test_normalise_truth_is_nfc_single_spaced():
    assert normalise_truth("á  torre\t x") == "á torre x"


def test_ground_truth_writes_line_images_gt_and_index(tmp_path: Path):
    pymupdf = pytest.importorskip("pymupdf")
    blind_index, open_index = _blind_page_index("Livro")
    pdf = tmp_path / "Livro.pdf"
    doc = pymupdf.open()
    for _ in range(max(blind_index, open_index) + 1):
        page = doc.new_page(width=400, height=600)
        page.insert_text((50, 108), "1.e4 e5 2.Cf3 Cc6", fontsize=9)
        page.insert_text((50, 123), "a torre pertence", fontsize=9)
    doc.save(pdf)
    doc.close()
    project = LabelProject.open_or_create(tmp_path / "proj", reviewer="ana")
    project.add_document(pdf)
    open_page = _page("Livro", open_index, pdf_path=str(pdf))
    blind_page = _page("Livro", blind_index, pdf_path=str(pdf))
    for pg in (open_page, blind_page):
        project.put_page(pg)
        for line in pg.regions[0].lines[:2]:
            project.decide(pg, line, LineStatus.ACCEPTED)
        project.decide(pg, pg.regions[0].lines[2], LineStatus.REJECTED)
    report = write_ground_truth(project, tmp_path / "gt")
    assert report.written == 2
    assert report.withheld_blind == 2
    assert blind_page.blind_regions == 1
    assert open_page.blind_regions == 0
    names = sorted(p.name for p in (tmp_path / "gt").glob("*.png"))
    assert names == [f"Livro_p{open_index}_r0_l0.png", f"Livro_p{open_index}_r0_l1.png"]
    assert (tmp_path / "gt" / f"Livro_p{open_index}_r0_l0.gt.txt").read_text(
        "utf-8"
    ) == "1.e4 e5 2.Cf3 Cc6 3.Bb5 a6 4.Ba4 Cf6\n"
    split = partition_split(tmp_path / "gt" / "index.jsonl")
    assert sum(len(v) for v in split.values()) == 2
    assert "blind" not in split
    from PIL import Image

    with Image.open(tmp_path / "gt" / names[0]) as image:
        assert image.height > 20
        assert image.width > image.height


# --------------------------------------------------------------------------- #
# Recognition → labels, with a fake service
# --------------------------------------------------------------------------- #


@dataclass
class _Word:
    text: str
    confidence: float
    box: object


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
    lines: tuple = ()


@dataclass
class _Candidate:
    variant: str
    engine: str
    result: _Result


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


class _FakeService:
    lang = "por+eng"

    def recognize_image(self, image, *, dpi, lang="", page_index=0):
        from caissa.ocr.types import BBox

        scale = dpi / 72.0
        w1 = _Word("Olá", 0.98, BBox(50 * scale, 100 * scale, 30 * scale, 10 * scale))
        w2 = _Word("mundo", 0.40, BBox(85 * scale, 100 * scale, 40 * scale, 10 * scale))
        line = _Line((w1, w2), BBox(50 * scale, 100 * scale, 75 * scale, 10 * scale))
        line2 = _Line(
            (_Word("segundo", 0.9, BBox(50 * scale, 130 * scale, 60 * scale, 10 * scale)),),
            BBox(50 * scale, 130 * scale, 60 * scale, 10 * scale),
            paragraph_index=1,
        )
        other = _Line((_Word("Olá", 0.9, w1.box), _Word("mundo!", 0.9, w2.box)), line.box)
        decision = SimpleNamespace(decision="review", reasons_pt=("Escore 0.70 abaixo do limite",))
        region = _Region(
            0,
            "page",
            BBox(0, 0, 400 * scale, 600 * scale),
            _Result((line, line2)),
            decision,
            candidates=(
                _Candidate("original", "tesseract", _Result((line, line2))),
                _Candidate("upscale", "tesseract", _Result((other,))),
            ),
        )
        return _Recognition(dpi=dpi, regions=[region])


def test_label_page_lays_out_lines_in_points_with_alternatives(tmp_path: Path):
    pymupdf = pytest.importorskip("pymupdf")
    from caissa.ocr.labeling.recognise import label_page, recognise_rect

    pdf = tmp_path / "Livro.pdf"
    doc = pymupdf.open()
    doc.new_page(width=400, height=600)
    doc.save(pdf)
    doc.close()
    page = label_page(_FakeService(), pdf, "Livro", 0, dpi=300, lang="por+eng")
    assert page.width_pt == 400
    assert page.engines == {"tesseract": "5.5"}
    # A whole-page region is split by the engine's own paragraphs.
    assert [r.kind for r in page.regions] == ["paragraph", "paragraph"]
    first = page.regions[0]
    assert first.rect == (50.0, 100.0, 125.0, 110.0)
    line = first.lines[0]
    assert line.hypothesis == "Olá mundo"
    assert line.box == (50.0, 100.0, 125.0, 110.0)
    assert line.low_confidence_words(0.85) == ("mundo",)
    assert line.alternatives == (("upscale/tesseract", "Olá mundo!"),)
    assert first.reasons == ("Escore 0.70 abaixo do limite",)
    assert first.prose_lang == "pt"
    drawn = recognise_rect(_FakeService(), page, (200, 300, 100, 200))
    assert drawn.drawn
    assert drawn.rect == (100, 200, 200, 300)
    assert drawn.index == 2
    assert drawn.lines[0].box[0] == pytest.approx(150.0), "boxes are offset by the clip origin"
