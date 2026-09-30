"""``caissa.ocr.diagram_decisions`` -- the contract of OCR_UI_ROADMAP_C2 §1.1.

The module is the diagram counterpart of ``ReviewDecisions``: one decision per
(page, box), matched by IoU ≥ 0,5, saved next to the labelling project under
the same slug.  Nothing here touches the real ``labeling/``: every path goes
through ``root=`` or the :data:`ENV_ROOT` variable pointed at ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from caissa.ocr.diagram_decisions import (
    ENV_ROOT,
    DiagramDecision,
    DiagramDecisions,
    decisions_dir,
    decisions_path,
    record,
)

FEN_A = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"
FEN_B = "8/8/8/4k3/8/8/4K3/4R3 b - - 0 1"
BOX = (72.0, 120.0, 272.0, 320.0)
NEAR = (75.0, 124.0, 276.0, 324.0)   # IoU ≈ 0,94 with BOX
FAR = (300.0, 120.0, 500.0, 320.0)   # no overlap


def _decision(fen: str = FEN_A, rect=BOX, page: int = 3, **kw) -> DiagramDecision:
    return DiagramDecision.now(page, rect, fen, source="teste", **kw)


def test_a_decision_carries_the_side_of_its_fen_and_refuses_nonsense() -> None:
    assert _decision(FEN_B).side == "b"
    assert _decision(FEN_A).side == "w"
    with pytest.raises(ValueError, match="lado"):
        DiagramDecision(page_index=0, rect=BOX, fen=FEN_A, side="x", decided_at="")
    with pytest.raises(ValueError, match="FEN"):
        DiagramDecision(page_index=0, rect=BOX, fen="  ", side="w", decided_at="")


def test_match_is_by_page_and_overlap_at_half_iou() -> None:
    decisions = DiagramDecisions().add(_decision())
    assert decisions.match(3, NEAR) is not None
    assert decisions.match(3, FAR) is None
    assert decisions.match(4, BOX) is None, "outra página não casa, mesmo com a mesma caixa"
    assert decisions.match(3, NEAR, iou=0.99) is None, "o piso é um parâmetro"


def test_add_replaces_the_decision_of_the_same_box_and_keeps_the_others() -> None:
    decisions = DiagramDecisions().add(_decision(FEN_A)).add(_decision(FEN_A, rect=FAR))
    assert len(decisions) == 2
    corrected = decisions.add(_decision(FEN_B, rect=NEAR))
    assert len(corrected) == 2, "a mesma caixa (IoU ≥ 0,5) é substituída, não acumulada"
    assert corrected.match(3, BOX).fen == FEN_B
    assert corrected.match(3, FAR).fen == FEN_A


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    decisions = DiagramDecisions(document="livro.pdf").add(_decision(reviewer="ana", note="n"))
    path = decisions.save(tmp_path / "sub" / "livro.json")
    back = DiagramDecisions.load(path)
    assert back == decisions
    assert back.items[0].reviewer == "ana"
    assert back.items[0].decided_at.endswith("+00:00")
    assert not path.with_suffix(".json.tmp").exists(), "a gravação é atômica e limpa o .tmp"


def test_decisions_path_uses_the_same_slug_as_review_decisions(tmp_path: Path, monkeypatch) -> None:
    from caissa.ocr.review import decisions_path as review_path

    pdf = Path(r"C:\livros\Aagaard - Practical Chess Defence.pdf")
    assert decisions_path(pdf, root=tmp_path) == tmp_path / (review_path(pdf).stem + ".json")
    assert decisions_path(pdf, root=tmp_path).name == review_path(pdf).name
    # The default folder sits next to `revisao/`, and the environment relocates it.
    assert decisions_dir().name == "diagramas"
    assert decisions_dir().parent == review_path(pdf).parent.parent
    monkeypatch.setenv(ENV_ROOT, str(tmp_path / "elsewhere"))
    assert decisions_dir() == tmp_path / "elsewhere"
    assert DiagramDecisions.for_pdf(pdf) is None


def test_record_loads_or_creates_adds_and_saves(tmp_path: Path) -> None:
    pdf = tmp_path / "livro.pdf"
    first = record(pdf, _decision(FEN_A), root=tmp_path / "d")
    assert first == tmp_path / "d" / "livro.json"
    second = record(pdf, _decision(FEN_B, rect=NEAR), root=tmp_path / "d")
    assert second == first
    loaded = DiagramDecisions.for_pdf(pdf, root=tmp_path / "d")
    assert loaded is not None
    assert loaded.document == "livro.pdf"
    assert len(loaded) == 1
    assert loaded.match(3, BOX).fen == FEN_B
    record(pdf, _decision(FEN_A, rect=FAR, page=3), root=tmp_path / "d")
    assert len(DiagramDecisions.for_pdf(pdf, root=tmp_path / "d")) == 2


def test_apply_returns_the_hit_with_the_decision_or_the_hit_untouched() -> None:
    from caissa.core.model import RecognitionPath
    from caissa.ingest.pdf.importer import DiagramHit

    decisions = DiagramDecisions().add(_decision(FEN_B))
    hit = DiagramHit(box=NEAR, fen=FEN_A, confidence=0.7, path=RecognitionPath.NEURAL,
                     method="contour", square_confidences=(0.5,) * 64)
    applied = decisions.apply(hit, 3)
    assert applied.fen == FEN_B
    assert applied.method == "human"
    assert applied.path is RecognitionPath.MANUAL
    assert applied.confidence == 1.0
    assert set(applied.square_confidences) == {1.0}
    assert decisions.apply(hit, 4) is hit
    # Anything with a `.box` will do: the module does not import the importer.
    assert decisions.apply(SimpleNamespace(box=FAR), 3).box == FAR
