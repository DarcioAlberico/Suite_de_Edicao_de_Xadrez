"""Negative samples and rare-class oversampling for the fine-tune (OCR_UI_ROADMAP passo 4).

The book model measured in ``ROTULAGEM.md`` §4c learned the figurines of
its book and learned, with them, to *see* figurines in noise: it wrote
``♖ … ♘♔R♗!`` on the ``photo`` control and invented moves on dithered
typeset pages.  The lines it trained on were all clean strips of one
scan; nothing in them said what texture without a piece looks like.

Two remedies, both about what enters ``list.train``:

* **Negatives** — prose lines of the book whose truth carries **no
  figurine**, re-rendered under the textures the controls and the
  degraded strata use (the ``photo`` vignette, pure noise, damp stains,
  fax dither) **with texture-only margins on both sides**, truth
  unchanged.  ``lstmtraining`` skips a sample whose truth is empty
  (``Empty truth string``), so a strip of pure texture cannot be a sample;
  the margins are how the model is told that texture resolves to nothing
  — measured: without them (first try, 120 negatives) the ``photo``
  control still came out ``De ♕a1``.
* **Oversampling** — a piece whose lines are fewer than the median piece's
  gets its lines repeated in the list until it reaches a share of the
  median (§4c: ♔ with 29 lines came out 0/13; ``lstmtraining`` reads a
  repeated path as another sample).

Only :mod:`numpy` and Pillow are used, so the unit tests can run the
generators on a synthetic strip.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from statistics import median

import numpy as np
from numpy.typing import NDArray

from caissa.ocr.controls import CONTROL_GENERATORS
from caissa.ocr.golden import ControlKind

__all__ = [
    "FIGURINES",
    "NEGATIVE_KINDS",
    "degrade",
    "make_negatives",
    "oversample",
    "piece_counts",
]

FIGURINES = "♔♕♖♗♘♙♚♛♜♝♞♟"
Strip = NDArray[np.uint8]
NEGATIVE_KINDS: tuple[str, ...] = ("photo", "noise", "stains", "dither")
#: What the training dialogs propose (the values measured on the SFC4 in
#: ``OCR_UI_REPORT_C1.md`` §7; ``0`` / ``0.0`` is the fine-tune of §4c).
RECOMMENDED_NEGATIVES = 120
RECOMMENDED_OVERSAMPLE = 1.0


#: Texture-only margins added to each side of a negative, as a share of
#: the line's width.  The truth stays the line's text, so the CTC has to
#: emit *nothing* over the margins — that is the supervision "texture is
#: not a piece" that a plain degraded line cannot give (``lstmtraining``
#: skips an empty truth, so a strip of pure texture cannot be a sample).
MARGIN_SHARE = (0.3, 0.8)


def _padded(strip: Strip, rng: np.random.Generator) -> tuple[Strip, slice]:
    """The line on white paper with texture-sized margins; where the line sits."""
    h, w = strip.shape
    left = int(w * rng.uniform(*MARGIN_SHARE))
    right = int(w * rng.uniform(*MARGIN_SHARE))
    paper = int(np.percentile(strip, 90))
    out = np.full((h, left + w + right), paper, dtype=np.uint8)
    out[:, left:left + w] = strip
    return out, slice(left, left + w)


def _photo(strip: Strip, rng: np.random.Generator) -> Strip:
    """The line printed over the ``photo`` control's vignette, vignette around it."""
    padded, _ = _padded(strip, rng)
    h, w = padded.shape
    texture = CONTROL_GENERATORS[ControlKind.PHOTO](h, w, rng).astype(np.float32)
    ink = 255.0 - padded.astype(np.float32)
    out = texture - ink * rng.uniform(0.55, 0.85)
    return np.clip(out + rng.normal(0, 4, size=padded.shape), 0, 255).astype(np.uint8)


def _noise(strip: Strip, rng: np.random.Generator) -> Strip:
    """Gaussian grain plus salt-and-pepper speckle, grain-only margins."""
    padded, _ = _padded(strip, rng)
    out = padded.astype(np.float32) + rng.normal(0, rng.uniform(18, 32), size=padded.shape)
    speckle = rng.random(padded.shape) < rng.uniform(0.02, 0.06)
    out[speckle] = rng.integers(0, 256, size=int(speckle.sum()))
    return np.clip(out, 0, 255).astype(np.uint8)


def _stains(strip: Strip, rng: np.random.Generator) -> Strip:
    """Damp blotches multiplied into the paper, blotches-only margins."""
    padded, _ = _padded(strip, rng)
    h, w = padded.shape
    texture = CONTROL_GENERATORS[ControlKind.STAINS](h, w, rng).astype(np.float32) / 255.0
    out = padded.astype(np.float32) * np.clip(texture, 0.35, 1.0)
    return np.clip(out, 0, 255).astype(np.uint8)


def _dither(strip: Strip, rng: np.random.Generator) -> Strip:
    """Fax: one bit per pixel after noisy thresholding, with dropout.

    The margins dither to salt-and-pepper.
    """
    padded, _ = _padded(strip, rng)
    noisy = padded.astype(np.float32) + rng.normal(0, rng.uniform(30, 50), size=padded.shape)
    out = np.where(noisy > rng.uniform(110, 150), 255, 0).astype(np.uint8)
    dropout = rng.random(padded.shape) < rng.uniform(0.01, 0.04)
    out[dropout] = 255
    return out


DEGRADATIONS: dict[str, Callable[[Strip, np.random.Generator], Strip]] = {
    "photo": _photo,
    "noise": _noise,
    "stains": _stains,
    "dither": _dither,
}


def degrade(strip: Strip, kind: str, *, seed: int = 0) -> Strip:
    """One degraded copy of a grey line strip, deterministic per seed."""
    if strip.ndim != 2:  # noqa: PLR2004 - a grey image has two axes
        raise ValueError("a tira tem de ser cinza (2-D)")
    return DEGRADATIONS[kind](strip, np.random.default_rng(seed))


def _has_figurine(text: str) -> bool:
    return any(ch in FIGURINES for ch in text)


def make_negatives(
    gt_dir: Path | str,
    names: Sequence[str],
    out_dir: Path | str,
    *,
    count: int,
    seed: int = 7,
    kinds: Sequence[str] = NEGATIVE_KINDS,
) -> list[str]:
    """Write ``count`` negative lines into ``out_dir`` and return their names.

    Sources are the lines of ``names`` (in ``gt_dir``) whose truth has no
    figurine, cycled in a seeded shuffle; the kinds cycle too, so every
    texture gets its share.  Each negative is ``<name>.png`` + ``<name>.gt.txt``
    in ``out_dir``, laid out like a ground-truth directory.
    """
    from PIL import Image

    gt = Path(gt_dir)
    out = Path(out_dir)
    if count <= 0:
        return []
    sources = [
        n for n in names
        if not _has_figurine((gt / f"{n}.gt.txt").read_text("utf-8").strip("\r\n"))
    ]
    if not sources:
        return []
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    order = list(sources)
    rng.shuffle(order)
    made: list[str] = []
    for k in range(count):
        source = order[k % len(order)]
        kind = kinds[k % len(kinds)]
        with Image.open(gt / f"{source}.png") as handle:
            strip = np.asarray(handle.convert("L"), dtype=np.uint8)
        degraded = degrade(strip, kind, seed=seed * 100_003 + k)
        name = f"neg_{kind}_{k:04d}_{source}"
        Image.fromarray(degraded).save(out / f"{name}.png")
        text = (gt / f"{source}.gt.txt").read_text("utf-8").strip("\r\n")
        (out / f"{name}.gt.txt").write_text(text + "\n", encoding="utf-8")
        made.append(name)
    return made


def piece_counts(texts: dict[str, str]) -> dict[str, int]:
    """How many lines (by name → truth) carry each figurine."""
    counts: Counter[str] = Counter()
    for text in texts.values():
        for piece in {ch for ch in text if ch in FIGURINES}:
            counts[piece] += 1
    return dict(counts)


def oversample(texts: dict[str, str], *, share: float) -> tuple[list[str], dict[str, int]]:
    """Extra copies of the lines of rare pieces.

    A piece is rare when fewer lines carry it than ``share × median`` (the
    median over the pieces present).  Its lines are repeated, round-robin,
    until it reaches that target; a line that carries two rare pieces
    counts for both.  Returns the extra names (with repetitions) and, per
    piece, how many copies were added.
    """
    if share <= 0:
        return [], {}
    counts = piece_counts(texts)
    if not counts:
        return [], {}
    target = math.ceil(median(counts.values()) * share)
    extras: list[str] = []
    added: dict[str, int] = {}
    have = dict(counts)
    for piece in sorted(counts, key=lambda p: (counts[p], FIGURINES.index(p))):
        if have[piece] >= target:
            continue
        lines = [n for n, t in texts.items() if piece in t]
        i = 0
        while have[piece] < target:
            name = lines[i % len(lines)]
            extras.append(name)
            for other in {ch for ch in texts[name] if ch in FIGURINES}:
                have[other] = have.get(other, 0) + 1
            added[piece] = added.get(piece, 0) + 1
            i += 1
    return extras, added
