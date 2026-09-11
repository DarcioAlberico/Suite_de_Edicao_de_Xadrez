"""``benchmarks/field_corrections.json`` is a ruler. A ruler needs a test.

The headline number of ``docs/quality/F4_FIELD_REPORT.md`` -- ``field_exact`` 0,9894
against 0,9787 -- turns on a single entry in this file. Two ways that can rot silently:

* the field set changes and the entry stops matching, so the overlay quietly applies to
  nothing and the "corrected" number becomes the raw one wearing a corrected label;
* someone adds an entry without the evidence that ``field_corrections.json`` demands, and
  the file stops being auditable.

Both are checked here. The first needs the trunk and skips without it; the schema checks
never skip.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from caissa.vision.classify.cvoff import ensure_cvoff_on_path

CORRECTIONS = Path(__file__).resolve().parents[3] / "benchmarks" / "field_corrections.json"

try:
    CVOFF_ROOT: Path | None = ensure_cvoff_on_path()
except FileNotFoundError:  # pragma: no cover - only on a machine without the trunk
    CVOFF_ROOT = None

needs_trunk = pytest.mark.skipif(CVOFF_ROOT is None, reason="tronco ChessVisionOFF_Puro ausente")


@pytest.fixture(scope="module")
def entries() -> list[dict]:
    return json.loads(CORRECTIONS.read_text(encoding="utf-8"))["corrections"]


class TestSchema:
    def test_the_file_exists_and_parses(self) -> None:
        data = json.loads(CORRECTIONS.read_text(encoding="utf-8"))
        assert "corrections" in data
        assert "_readme" in data, "o arquivo tem de dizer para que serve e qual e a barra de entrada"

    def test_every_entry_carries_its_evidence(self, entries: list[dict]) -> None:
        """A correction nobody can check is a correction nobody should trust."""
        for entry in entries:
            assert entry["evidence"], f"{entry['pdf']} p{entry['page']} sem evidencia"
            assert len("\n".join(entry["evidence"])) > 200, "evidencia curta demais para ser conferida"
            assert entry["verified_by"]

    def test_every_entry_names_the_squares_it_changes(self, entries: list[dict]) -> None:
        for entry in entries:
            assert entry["squares"], "a correcao tem de dizer quais casas mudam"
            assert len(entry["squares"]) == _differing(entry["from"], entry["to"])

    def test_from_and_to_are_different_and_well_formed(self, entries: list[dict]) -> None:
        for entry in entries:
            assert entry["from"] != entry["to"]
            for placement in (entry["from"], entry["to"]):
                assert placement.count("/") == 7

    def test_entries_are_unique(self, entries: list[dict]) -> None:
        keys = [(e["pdf"], e["page"], e["diagram"]) for e in entries]
        assert len(keys) == len(set(keys))


def _differing(left: str, right: str) -> int:
    from chess_diagram_ocr.fen_utils import labels_from_fen

    a, b = labels_from_fen(left), labels_from_fen(right)
    return sum(1 for i in range(64) if a[i] != b[i])


@needs_trunk
class TestStillApplies:
    def test_every_correction_finds_its_annotated_diagram(self, entries: list[dict]) -> None:
        """If this fails, the field set moved and the overlay must be re-justified, not re-pointed."""
        from chess_diagram_ocr.field_eval import load_field_set

        assert CVOFF_ROOT is not None
        pages = {(p.pdf, p.page): p for p in load_field_set(CVOFF_ROOT / "data" / "field_set.jsonl")}
        for entry in entries:
            page = pages.get((entry["pdf"], entry["page"]))
            assert page is not None, f"{entry['pdf']} p{entry['page']} nao esta mais no conjunto de campo"
            assert entry["diagram"] < len(page.diagrams)
            assert page.diagrams[entry["diagram"]].placement == entry["from"], (
                "a anotacao mudou; a correcao precisa ser revista antes de qualquer medicao"
            )

    def test_the_corrected_placement_is_legal(self, entries: list[dict]) -> None:
        """A correction that produces an illegal position is a worse annotation, not a better one."""
        from chess_diagram_ocr.fen_utils import check_position

        for entry in entries:
            assert check_position(entry["to"] + " w - - 0 1").is_fatal is False

    def test_the_squares_named_are_the_squares_that_change(self, entries: list[dict]) -> None:
        from chess_diagram_ocr.config import PIECE_CLASSES
        from chess_diagram_ocr.fen_utils import labels_from_fen

        files = "abcdefgh"
        for entry in entries:
            before, after = labels_from_fen(entry["from"]), labels_from_fen(entry["to"])
            named = set()
            for item in entry["squares"]:
                square, _, change = item.partition(" ")
                old, _, new = change.partition("->")
                named.add((square, old, new))
            actual = set()
            for index in range(64):
                if before[index] == after[index]:
                    continue
                name = f"{files[index % 8]}{8 - index // 8}"
                actual.add((name, PIECE_CLASSES[before[index]], PIECE_CLASSES[after[index]]))
            assert named == actual
