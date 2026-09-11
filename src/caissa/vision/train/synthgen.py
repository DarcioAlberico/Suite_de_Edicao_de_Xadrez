"""Synthetic diagram generator -- the gap ``docs/ASSETS.md`` 3 lists for F4.

# Origem: Chess_diagram_to_FEN/src/fen_recognition/generate_chessboards.py (Jost Triller, MIT)
# Absorvido em 2026-09-10. Alteracoes: e um ADAPTADOR, nao uma copia -- as primitivas de
# render (86 conjuntos de pecas, temas de tabuleiro, warp por peca, deslocamento de matiz,
# fundos procedurais) sao chamadas no clone original, e o que esta aqui e o controle que o
# treino deste projeto precisa e que o gerador de origem nao oferece:
#   1. **Escolha explicita do conjunto de pecas.** `generate_one` sorteia entre os 86. Medir
#      generalizacao exige separar conjuntos de treino dos de avaliacao, e um sorteio nao
#      permite isso. Aqui o chamador diz quais entram.
#   2. **Sem rede.** `_overlay_random_text` chama `_download_google_fonts`, que baixa fontes
#      da internet. Este acervo nao sai da maquina e este processo nao busca nada: a
#      sobreposicao de texto usa **fontes locais do Windows** ou fica desligada.
#   3. **Rotulo no vocabulario do tronco.** O tronco rotula por FEN de colocacao e corta em
#      casas com `BOARD_SIZE = 800`; o gerador de origem devolve um `Position` do proprio
#      projeto. A conversao mora aqui, num lugar so.
#   4. **Determinismo por indice.** Amostra `n` com semente `s` e sempre a mesma imagem, sem
#      guardar nada em disco. E o que torna um dataset sintetico *reproduzivel* sem custar os
#      gigabytes de PNG que a maquina nao tem (31,5 GB livres).

**Por que isto e apontado, e nao um "mais dados nunca faz mal".**
``benchmarks/style_coverage.py`` mede o classificador de producao sobre os 12 glifos limpos
de cada um dos 86 conjuntos, em casa clara e escura: **0,7548** de acerto, e a confusao
dominante e **``q -> Q``, 48 ocorrencias** -- dama preta lida como dama branca. E exatamente
a unica leitura exportada e errada que restou no conjunto de campo. O modelo de producao foi
treinado em 3.290 diagramas reais de um acervo so; o que falta a ele e **estilo**, e estilo e
o que este gerador produz.
"""

from __future__ import annotations

import contextlib
import os
import random
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "DEFAULT_TSOJ_ROOT",
    "SynthConfig",
    "SyntheticBoards",
    "available_piece_sets",
    "render_board",
    "split_piece_sets",
]

DEFAULT_TSOJ_ROOT = Path("C:/Python-Chess2/Chess_diagram_to_FEN")

BOARD_SIZE = 800
"""Matches ``chess_diagram_ocr.config.BOARD_SIZE``: the loader resizes to this anyway, and
generating at the target size keeps one resampling step out of the training image."""

PIECES = "PNBRQKpnbrqk"


@contextlib.contextmanager
def _cwd(path: Path) -> Iterator[None]:
    """``render_config`` resolves ``resources/pieces`` against the process directory."""
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


@lru_cache(maxsize=4)
def _module(root: Path) -> Any:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    with _cwd(root):
        import importlib

        return importlib.import_module("src.fen_recognition.generate_chessboards")


@lru_cache(maxsize=4)
def _sets(root: Path, tile: int) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
    generator = _module(root)
    with _cwd(root):
        from src.render_config import get_render_config

        config = get_render_config("chess")
        images = generator._load_piece_images("chess", tile)
    names = tuple(f"{item.provider}/{item.set_name}" for item in config.piece_sets)
    return names, tuple(images)


@lru_cache(maxsize=4)
def _themes(root: Path, width: int, height: int) -> tuple[Any, ...]:
    generator = _module(root)
    with _cwd(root):
        from src.render_config import list_board_theme_paths, open_board_theme

        return tuple(open_board_theme(p, board_w=width, board_h=height) for p in list_board_theme_paths("chess"))


@lru_cache(maxsize=1)
def _local_fonts() -> tuple[str, ...]:
    """Windows' own font directory. Nothing is downloaded; missing fonts just disable text."""
    root = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    if not root.is_dir():
        return ()
    return tuple(str(p) for p in sorted(root.glob("*.ttf"))[:60])


def available_piece_sets(root: Path = DEFAULT_TSOJ_ROOT, tile: int = BOARD_SIZE // 8) -> tuple[str, ...]:
    """The names of every piece set the clone ships, ``provider/set`` form."""
    return _sets(Path(root), tile)[0]


def split_piece_sets(
    names: Sequence[str], *, holdout: float = 0.34, seed: int = 20260910
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Deterministic train / held-out split **over styles**, not over images.

    Splitting rendered boards would leak: two boards from the same piece set are the same
    style, and a model that memorised that style scores on the held-out half without having
    generalised at all.  The unit of generalisation here is the *style*, so the split is over
    piece sets, by a fixed seed, and it is reported with every number measured on it.
    """
    ordered = sorted(names)
    rng = random.Random(seed)
    shuffled = ordered[:]
    rng.shuffle(shuffled)
    cut = max(1, int(round(len(shuffled) * holdout)))
    held = tuple(sorted(shuffled[:cut]))
    train = tuple(sorted(shuffled[cut:]))
    return train, held


@dataclass(frozen=True)
class SynthConfig:
    """What a synthetic board may contain. Every knob is measured, none is a default guess."""

    tsoj_root: Path = DEFAULT_TSOJ_ROOT
    piece_sets: tuple[str, ...] = ()
    """Empty means every set the clone ships. Name them to control train/held-out."""

    board_size: int = BOARD_SIZE
    warp_prob: float = 0.8
    """Per-piece projective warp, as in the source generator."""

    hue_prob: float = 0.5
    text_prob: float = 0.0
    """Random text overlay. **Off by default**: the source implementation downloads fonts."""

    invert_prob: float = 0.1
    """Whole-board inversion, with the piece colours relabelled to match."""

    min_pieces: int = 2
    max_pieces: int = 40
    """Random placements, not legal games: a per-square classifier learns glyphs, and a
    uniform draw over the twelve pieces is what gives the rare ones (queens, both colours)
    the exposure that a game distribution never would."""

    offset_ratio: float = 1 / 30
    """Per-piece jitter, in squares. The source uses ``tile // 30``."""

    themes: bool = True
    seed: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def _placement_from_grid(grid: list[str | None]) -> str:
    rows = []
    for row in range(8):
        out: list[str] = []
        run = 0
        for col in range(8):
            piece = grid[row * 8 + col]
            if piece is None:
                run += 1
                continue
            if run:
                out.append(str(run))
                run = 0
            out.append(piece)
        if run:
            out.append(str(run))
        rows.append("".join(out))
    return "/".join(rows)


def _flip_case(placement: str) -> str:
    return "".join(ch.swapcase() if ch.isalpha() else ch for ch in placement)


def render_board(config: SynthConfig, index: int) -> tuple[np.ndarray, str, str]:
    """One synthetic board: ``(rgb uint8 (S, S, 3), placement, piece_set_name)``.

    Deterministic in ``(config.seed, index)``: the same pair always yields the same image,
    which is what lets a synthetic dataset be reproducible without writing a single PNG.
    """
    from PIL import Image, ImageOps

    root = Path(config.tsoj_root)
    tile = config.board_size // 8
    generator = _module(root)
    names, images = _sets(root, tile)

    wanted = config.piece_sets or names
    allowed = [i for i, name in enumerate(names) if name in set(wanted)]
    if not allowed:
        raise ValueError(f"nenhum conjunto de pecas casou com {config.piece_sets!r}")

    rng = random.Random((config.seed * 1_000_003) ^ (index * 2_654_435_761))
    state = random.getstate()
    random.seed(rng.getrandbits(63))  # the clone's primitives use the module-level `random`
    try:
        chosen = rng.choice(allowed)
        set_name = names[chosen]
        pieces = dict(images[chosen])

        size = config.board_size
        if config.themes and _themes(root, size, size) and rng.random() < 0.75:
            background = rng.choice(list(_themes(root, size, size))).copy()
        elif rng.random() < 0.5:
            background = generator._noisy_gray_board(size, size).convert("RGBA")
        else:
            background = generator._random_uniform_board(size, size)
        if rng.random() < 0.5:
            background = ImageOps.mirror(background)
        if rng.random() < 0.5:
            background = ImageOps.flip(background)

        if rng.random() < config.warp_prob:
            pieces = {key: generator._warp_piece_image(img) for key, img in pieces.items()}
        if rng.random() < config.hue_prob:
            shift = rng.random()
            pieces = {key: generator._shift_hue(img, shift) for key, img in pieces.items()}

        grid: list[str | None] = [None] * 64
        count = rng.randint(config.min_pieces, config.max_pieces)
        for square in rng.sample(range(64), count):
            grid[square] = rng.choice(PIECES)

        board = background.copy()
        jitter = max(1, int(tile * config.offset_ratio))
        for square, piece in enumerate(grid):
            if piece is None:
                continue
            glyph = pieces[("w" if piece.isupper() else "b") + piece.lower()]
            x = (square % 8) * tile + rng.randint(-jitter, jitter)
            y = (square // 8) * tile + rng.randint(-jitter, jitter)
            board.paste(glyph, (x, y), glyph)

        image = board.convert("RGB")
        placement = _placement_from_grid(grid)
        if rng.random() < config.invert_prob:
            image = ImageOps.invert(image)
            placement = _flip_case(placement)
        if config.text_prob and rng.random() < config.text_prob and _local_fonts():
            image = _overlay_local_text(image, rng)

        array = np.asarray(image, dtype=np.uint8)
        if array.shape[:2] != (size, size):
            image = image.resize((size, size), Image.BILINEAR)
            array = np.asarray(image, dtype=np.uint8)
        return array, placement, set_name
    finally:
        random.setstate(state)


def _overlay_local_text(image: Any, rng: random.Random) -> Any:
    """Text overlay using fonts already on this machine. No download, ever."""
    from PIL import Image, ImageDraw, ImageFont

    fonts = _local_fonts()
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(rng.randint(1, 3)):
        try:
            font = ImageFont.truetype(rng.choice(fonts), rng.randint(image.size[0] // 40, image.size[0] // 12))
        except OSError:
            return image
        text = "".join(rng.choice("0123456789abcdefghijklmnopqrstuvwxyz.+-#!?") for _ in range(rng.randint(2, 12)))
        grey = rng.randint(0, 255)
        draw.text(
            (rng.randint(0, image.size[0]), rng.randint(0, image.size[1])),
            text,
            font=font,
            fill=(grey, grey, grey, rng.randint(60, 220)),
        )
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")


class SyntheticBoards:
    """A fixed-length, on-the-fly synthetic board dataset. Writes nothing to disk.

    ``__getitem__`` returns ``(board_rgb, placement)``; the caller cuts the 64 squares with
    the trunk's own ``BoardFenDataset.square`` machinery so that training and inference cut
    the image the same way.
    """

    def __init__(self, config: SynthConfig, length: int) -> None:
        self.config = config
        self.length = int(length)

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, index: int) -> tuple[np.ndarray, str]:
        if not 0 <= index < self.length:
            raise IndexError(index)
        board, placement, _set = render_board(self.config, index)
        return board, placement
