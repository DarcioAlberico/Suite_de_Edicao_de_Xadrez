"""The synthetic generator has to be reproducible, style-split and offline.

Those three are not incidental: they are what make a number measured against it mean
anything.  A generator that draws a different image for the same index cannot be
reproduced from a report; one that lets a piece set appear on both sides of the split
measures memorisation instead of coverage; and one that reaches the network violates the
rule that this collection and this process stay on the machine
(``docs/quality/CORPUS.md`` 0).  The source generator does reach the network -- its text
overlay downloads Google Fonts -- so "offline" here is an assertion about a real difference
between the adapter and its origin, not a truism.

The pure-logic tests never skip.  The rendering tests need the ``Chess_diagram_to_FEN``
clone and skip without it, and the label round-trip needs the trunk.
"""

from __future__ import annotations

import socket
from pathlib import Path

import numpy as np
import pytest

from caissa.vision.classify.cvoff import ensure_cvoff_on_path
from caissa.vision.train import synthgen
from caissa.vision.train.synthgen import SynthConfig, SyntheticBoards, split_piece_sets

try:
    CVOFF_ROOT: Path | None = ensure_cvoff_on_path()
except FileNotFoundError:  # pragma: no cover - only on a machine without the trunk
    CVOFF_ROOT = None

needs_trunk = pytest.mark.skipif(CVOFF_ROOT is None, reason="tronco ChessVisionOFF_Puro ausente")

CLONE = synthgen.DEFAULT_TSOJ_ROOT
needs_clone = pytest.mark.skipif(
    not (CLONE / "src" / "fen_recognition" / "generate_chessboards.py").is_file(),
    reason=f"Chess_diagram_to_FEN nao esta em {CLONE}",
)

SMALL = 256
"""A 256 px board is 32 px squares -- enough to place a glyph, cheap enough for a unit test."""

ONE_SET = ("lichess/alpha",)


class TestPlacementEncoding:
    def test_empty_grid_is_eight_eights(self) -> None:
        assert synthgen._placement_from_grid([None] * 64) == "8/8/8/8/8/8/8/8"

    def test_runs_of_empties_collapse(self) -> None:
        grid: list[str | None] = [None] * 64
        grid[0] = "r"
        grid[7] = "k"
        assert synthgen._placement_from_grid(grid).split("/")[0] == "r6k"

    def test_full_rank_has_no_digits(self) -> None:
        grid: list[str | None] = [None] * 64
        for col in range(8):
            grid[col] = "P"
        assert synthgen._placement_from_grid(grid).split("/")[0] == "PPPPPPPP"

    def test_flip_case_swaps_colour_and_leaves_the_digits_alone(self) -> None:
        assert synthgen._flip_case("rnbq4/8/8/8/8/8/8/4QBNR") == "RNBQ4/8/8/8/8/8/8/4qbnr"

    @needs_trunk
    def test_round_trips_through_the_trunk_label_decoder(self) -> None:
        """The placement string exists so the trunk can label it; nothing else validates it."""
        from chess_diagram_ocr.config import PIECE_CLASSES
        from chess_diagram_ocr.fen_utils import labels_from_fen

        grid: list[str | None] = [None] * 64
        grid[0], grid[9], grid[63] = "q", "N", "k"
        labels = labels_from_fen(synthgen._placement_from_grid(grid))
        assert len(labels) == 64
        assert PIECE_CLASSES[labels[0]] == "q"
        assert PIECE_CLASSES[labels[9]] == "N"
        assert PIECE_CLASSES[labels[63]] == "k"
        assert sum(1 for value in labels if PIECE_CLASSES[value] != "empty") == 3


class TestStyleSplit:
    def test_split_is_disjoint_and_total(self) -> None:
        names = tuple(f"prov/{i:02d}" for i in range(30))
        train, held = split_piece_sets(names)
        assert set(train) & set(held) == set()
        assert set(train) | set(held) == set(names)

    def test_split_is_deterministic(self) -> None:
        names = tuple(f"prov/{i:02d}" for i in range(30))
        assert split_piece_sets(names) == split_piece_sets(names)

    def test_split_does_not_depend_on_input_order(self) -> None:
        """A caller listing the sets differently must get the same holdout, or two reports
        that both say "held out" would not mean the same thing."""
        names = [f"prov/{i:02d}" for i in range(30)]
        assert split_piece_sets(names) == split_piece_sets(list(reversed(names)))

    def test_holdout_fraction_is_honoured(self) -> None:
        names = tuple(f"prov/{i:02d}" for i in range(100))
        _train, held = split_piece_sets(names, holdout=0.25)
        assert len(held) == 25

    def test_holdout_is_never_empty(self) -> None:
        _train, held = split_piece_sets(("a/one", "a/two"), holdout=0.01)
        assert len(held) == 1

    def test_a_different_seed_gives_a_different_split(self) -> None:
        names = tuple(f"prov/{i:02d}" for i in range(40))
        assert split_piece_sets(names, seed=1) != split_piece_sets(names, seed=2)


class TestOffline:
    def test_the_adapter_imports_nothing_that_can_reach_the_network(self) -> None:
        """Checked on the parse tree, not on the text: the module *names*
        ``_download_google_fonts`` in its docstring, to say what it deliberately left behind."""
        import ast

        tree = ast.parse(Path(synthgen.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not imported & {"urllib", "requests", "http", "socket", "ftplib", "gdown"}

    def test_the_adapter_never_calls_the_font_downloader(self) -> None:
        import ast

        tree = ast.parse(Path(synthgen.__file__).read_text(encoding="utf-8"))
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert "_download_google_fonts" not in called
        assert "_overlay_random_text" not in called

    def test_text_overlay_is_off_by_default(self) -> None:
        assert SynthConfig().text_prob == 0.0

    def test_local_fonts_come_from_the_machine(self) -> None:
        for path in synthgen._local_fonts():
            assert Path(path).is_file()
            assert Path(path).suffix.lower() == ".ttf"

    @needs_clone
    @pytest.mark.slow
    def test_a_render_opens_no_socket(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: object, **kwargs: object) -> None:
            raise AssertionError("o gerador tentou abrir um socket")

        monkeypatch.setattr(socket.socket, "connect", refuse)
        board, placement, _name = synthgen.render_board(
            SynthConfig(piece_sets=ONE_SET, board_size=SMALL, text_prob=1.0), 0
        )
        assert board.shape == (SMALL, SMALL, 3)
        assert placement.count("/") == 7


@needs_clone
class TestRendering:
    @pytest.mark.slow
    def test_same_index_gives_the_same_image(self) -> None:
        config = SynthConfig(piece_sets=ONE_SET, seed=3, board_size=SMALL)
        first, first_fen, first_set = synthgen.render_board(config, 11)
        second, second_fen, second_set = synthgen.render_board(config, 11)
        assert np.array_equal(first, second)
        assert first_fen == second_fen
        assert first_set == second_set == ONE_SET[0]

    @pytest.mark.slow
    def test_different_indices_give_different_images(self) -> None:
        config = SynthConfig(piece_sets=ONE_SET, seed=3, board_size=SMALL)
        first, _, _ = synthgen.render_board(config, 0)
        second, _, _ = synthgen.render_board(config, 1)
        assert not np.array_equal(first, second)

    @pytest.mark.slow
    def test_a_different_seed_gives_a_different_image_at_the_same_index(self) -> None:
        one, _, _ = synthgen.render_board(SynthConfig(piece_sets=ONE_SET, seed=1, board_size=SMALL), 4)
        two, _, _ = synthgen.render_board(SynthConfig(piece_sets=ONE_SET, seed=2, board_size=SMALL), 4)
        assert not np.array_equal(one, two)

    @pytest.mark.slow
    def test_shape_and_dtype_match_a_trunk_board(self) -> None:
        board, _, _ = synthgen.render_board(SynthConfig(piece_sets=ONE_SET, seed=1, board_size=SMALL), 5)
        assert board.shape == (SMALL, SMALL, 3)
        assert board.dtype == np.uint8

    @pytest.mark.slow
    def test_unknown_piece_set_is_refused(self) -> None:
        with pytest.raises(ValueError, match="nenhum conjunto"):
            synthgen.render_board(SynthConfig(piece_sets=("nao/existe",), board_size=SMALL), 0)

    @needs_trunk
    @pytest.mark.slow
    def test_the_piece_budget_is_respected(self) -> None:
        from chess_diagram_ocr.config import PIECE_CLASSES
        from chess_diagram_ocr.fen_utils import labels_from_fen

        config = SynthConfig(piece_sets=ONE_SET, seed=9, board_size=SMALL, min_pieces=4, max_pieces=6)
        for index in range(4):
            _board, placement, _name = synthgen.render_board(config, index)
            labels = labels_from_fen(placement)
            occupied = sum(1 for value in labels if PIECE_CLASSES[value] != "empty")
            assert 4 <= occupied <= 6

    @pytest.mark.slow
    def test_dataset_length_and_bounds(self) -> None:
        data = SyntheticBoards(SynthConfig(piece_sets=ONE_SET, board_size=SMALL), 3)
        assert len(data) == 3
        board, placement = data[2]
        assert board.shape[0] == SMALL
        assert placement.count("/") == 7
        with pytest.raises(IndexError):
            _ = data[3]

    @pytest.mark.slow
    def test_render_leaves_the_global_random_state_alone(self) -> None:
        """The clone's primitives draw from module-level ``random``; borrowing it must be
        invisible, or a caller that seeded ``random`` would silently get another stream."""
        import random

        random.seed(1234)
        expected = [random.random() for _ in range(3)]
        random.seed(1234)
        synthgen.render_board(SynthConfig(piece_sets=ONE_SET, board_size=SMALL), 0)
        assert [random.random() for _ in range(3)] == expected

    @pytest.mark.slow
    def test_render_leaves_the_working_directory_alone(self) -> None:
        """``render_config`` resolves its resources against the process directory, so the
        adapter has to chdir -- and has to change it back."""
        before = Path.cwd()
        synthgen.render_board(SynthConfig(piece_sets=ONE_SET, board_size=SMALL), 1)
        assert Path.cwd() == before

    @pytest.mark.slow
    def test_the_clone_ships_the_catalogue_the_report_cites(self) -> None:
        assert len(synthgen.available_piece_sets(tile=SMALL // 8)) == 86
