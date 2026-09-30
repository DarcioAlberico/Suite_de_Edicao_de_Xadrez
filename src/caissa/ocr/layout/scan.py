"""Layout for a page that has no text layer — OCR_UI_ROADMAP_C2 passo B1.

A born-digital page gets its layout for free from the text layer.  A scanned
page has nothing to lay out until something has read it, so until this module
existed it went to the cascade as **one region** in PSM 3 — and Tesseract's
own segmentation, good as it is on a column, merges the two columns of a
two-column page into single lines that cross the gutter.  Measured on the
golden corpus (``docs/quality/sol/c1_anchor.json``, recounted in
``OCR_UI_ANALISE_C2.md`` §4.2): ``scan_clean_300`` single-column CER 0,0052,
two-column **0,1254**; ``twocol:d:9`` comes back as five lines of ~2.300 px
across a 90 px gutter, accepted at 0,927, CER 0,688.

The method is the trunk's (``chess_diagram_ocr.text.colunas``, S-190/S-191,
measured on 456 pages of four books: Nunn 316/352, Aagaard 28/30, Darcy Lima
0/39 as the single-column control), applied to what the whole-page pass
already produced instead of to connected components:

1.  **Project lines, not boxes.**  For every x, count how many *lines* cover
    it, where a line covers the union of its **word** boxes — words never
    cross a gutter, only Tesseract's merged line box does.  A gutter is a run
    of x wide enough (0,8 median character widths, 1 % of the text width, 4 px
    — the trunk's three floors) that at most one line crosses, and that one
    only on a page with at least twelve lines: the centred running head sits
    on the gutter, and on a page of five lines "one" is 20 % and invents
    columns.
2.  **A gutter has to leave columns behind.**  A band narrower than 10 % of
    the text width is merged into its neighbour, not kept: the gap between a
    contents title and its page number is wide, and treating it as a gutter
    reads all the titles and then all the numbers.
3.  **Split the lines at the gutters** — each line's words are dealt to the
    column band their centre falls in, one new line per band — and hand the
    result to :func:`~caissa.ocr.layout.analyze.analyze_page`, which now sees
    lines that sit in columns and orders them the way it orders a text layer.
4.  **Tag movetext.**  A region most of whose tokens are moves is
    :attr:`RegionKind.MOVETEXT`: the page loop then reads it in PSM 6 with the
    movetext profile, and the service's profile and glyph candidates see a
    region of notation instead of a page of prose (``games_gate`` Nunn 0/99:
    "the moves live in the prose").

What it does **not** do: touch a page where no interior gutter is found.  A
single-column page keeps the whole-page reading exactly as it was — the
justified spaces of forty lines never line up, so no x survives the count
(``LINHAS_NA_CALHA=1``, control 0/39).  ``test_scan_layout`` pins both sides.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from ..types import BBox, OcrLine, OcrResult, RegionKind
from .analyze import (
    LayoutConfig,
    LayoutInput,
    LayoutLine,
    LayoutRegion,
    PageLayout,
    RunningFurnitureDetector,
    analyze_page,
)

__all__ = ["ScanLayout", "ScanLayoutConfig", "find_gutters", "scan_layout", "split_at_gutters"]


@dataclass(frozen=True, slots=True)
class ScanLayoutConfig:
    """The trunk's constants (``text/colunas.py``), with their measurements."""

    #: Minimum gutter width in median character widths.  The trunk measured
    #: real gutters at 1,00–3,31 and the widest gap that is not one at 0,75.
    gutter_in_chars: float = 0.8
    #: ...and in fractions of the text width, for the page whose median
    #: character width is meaningless (a halftone panel drags it to 2 px).
    gutter_page_frac: float = 0.01
    #: ...and never below this many pixels, at any scale.
    gutter_min_px: int = 4
    #: A column narrower than this fraction of the text width is merged into
    #: its neighbour (2 % and 4 % were the false columns of a contents page;
    #: 48 % the real ones).
    column_min_frac: float = 0.10
    #: How many lines may cross a gutter without abolishing it.
    lines_in_gutter: int = 1
    #: ...from this many lines on; below it, none (one of five is 20 %).
    lines_to_tolerate: int = 12
    #: A page with fewer lines than this is not laid out: there is nothing to
    #: order and a gutter found in two lines is a coincidence.
    min_lines: int = 3
    #: More bands than this and the page is a **table**, not columns: every
    #: row of a results table has an entry in every band, so the gutters are
    #: as clean as a column's, and reading it band by band scrambles the rows
    #: (measured 2026-09-20 on ``table:2``: CER 0,0036 → 0,47 with the split).
    #: Chess books are set in one or two columns; a third band is a table.
    max_columns: int = 2
    #: A band whose median line is shorter than this many characters is not
    #: a column of prose: a **move list** prints White's moves and Black's in
    #: two aligned bands (``28 ♘f2 | ♗h4!``) with a gutter as clean as a
    #: page's, and reading it band by band puts every White move before every
    #: Black one (measured 2026-09-21, Dvoretsky ``18:179:252``: CER 0 → 0,62).
    #: A prose column runs 40–70 characters a line; a move column 4–10.
    min_band_chars: int = 16
    #: Share of a region's tokens that must be moves for it to be movetext.
    movetext_share: float = 0.5
    #: ...over at least this many tokens.
    movetext_min_tokens: int = 6
    #: The sabotage switch: a gutter of zero width is never found, and every
    #: scan goes back to one region (``SOL_CONFIG='{"page": {"scan":
    #: {"enabled": false}}}'`` in ``bench_sol``).
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ScanLayout:
    """What the scan pass decided: the layout and the lines it was built on."""

    layout: PageLayout
    #: The whole-page result with its lines split at the gutters, boxes in
    #: the raster's pixel space; ``layout`` is in the page's own units.
    result: OcrResult
    gutters: tuple[tuple[float, float], ...]
    notes: tuple[str, ...] = ()
    signals: dict[str, Any] = field(default_factory=dict)

    @property
    def columns(self) -> int:
        return len(self.gutters) + 1


# --------------------------------------------------------------------------- #
# Gutters
# --------------------------------------------------------------------------- #


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2] if ordered else 0.0


def _gutter_floor(lines: Sequence[OcrLine], text_width: float,
                  cfg: ScanLayoutConfig) -> float:
    """The trunk's ``piso_de_calha`` over words: three floors, the largest wins."""
    widths = [w.box.w / max(1, len(w.text)) for line in lines for w in line.words
              if w.text.strip() and w.box.w > 0]
    return max(_median(widths) * cfg.gutter_in_chars,
               text_width * cfg.gutter_page_frac,
               float(cfg.gutter_min_px))


def find_gutters(lines: Sequence[OcrLine], *,
                 config: ScanLayoutConfig | None = None) -> list[tuple[float, float]]:
    """Interior vertical gutters, in the lines' own pixel space.

    Empty when the page reads as one column.  The projection counts *lines*
    (the union of each line's word boxes), tolerates one crossing line on a
    page of twelve or more, and keeps a gap only when it is at least the
    floor wide and does not touch either edge of the text.
    """
    cfg = config or ScanLayoutConfig()
    lines = [line for line in lines if any(w.text.strip() for w in line.words)]
    if len(lines) < cfg.min_lines:
        return []
    x_min = min(w.box.x0 for line in lines for w in line.words)
    x_max = max(w.box.x1 for line in lines for w in line.words)
    width = x_max - x_min
    if width <= 1:
        return []
    bins = int(width) + 2
    coverage = np.zeros(bins, dtype=np.int32)
    for line in lines:
        mask = np.zeros(bins, dtype=bool)
        for word in line.words:
            if not word.text.strip():
                continue
            a = max(0, int(word.box.x0 - x_min))
            b = min(bins, int(np.ceil(word.box.x1 - x_min)) + 1)
            if b > a:
                mask[a:b] = True
        coverage += mask
    tolerated = cfg.lines_in_gutter if len(lines) >= cfg.lines_to_tolerate else 0
    free = coverage <= tolerated
    floor = _gutter_floor(lines, width, cfg)
    edges = np.diff(np.concatenate(([False], free, [False])).astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    gutters: list[tuple[float, float]] = []
    for a, b in zip(starts, ends, strict=True):
        # A free run touching either edge is a margin, not a gutter.
        if a == 0 or b >= bins - 1 or b - a < floor:
            continue
        gutters.append((x_min + float(a), x_min + float(b)))
    return _merge_narrow_bands(gutters, x_min, x_max, cfg)


def _merge_narrow_bands(gutters: list[tuple[float, float]], x_min: float, x_max: float,
                        cfg: ScanLayoutConfig) -> list[tuple[float, float]]:
    """Drop the gutters that leave a band too narrow to be a column, merging
    that band into the neighbour across the *narrower* gutter (the one that
    asserts less separation) — the trunk's ``_fundir_faixas_estreitas``."""
    if not gutters:
        return []
    minimum = (x_max - x_min) * cfg.column_min_frac
    bands: list[tuple[float, float]] = []
    cursor = x_min
    for a, b in gutters:
        bands.append((cursor, a))
        cursor = b
    bands.append((cursor, x_max))
    gaps = list(gutters)   # gaps[i] separates bands[i] and bands[i+1]
    while len(bands) > 1:
        i = min(range(len(bands)), key=lambda j: bands[j][1] - bands[j][0])
        if bands[i][1] - bands[i][0] >= minimum:
            break
        left = (gaps[i - 1][1] - gaps[i - 1][0]) if i else None
        right = (gaps[i][1] - gaps[i][0]) if i + 1 < len(bands) else None
        if right is None or (left is not None and left <= right):
            bands[i - 1:i + 1] = [(bands[i - 1][0], bands[i][1])]
            del gaps[i - 1]
        else:
            bands[i:i + 2] = [(bands[i][0], bands[i + 1][1])]
            del gaps[i]
    return gaps


# --------------------------------------------------------------------------- #
# Splitting
# --------------------------------------------------------------------------- #


def _band_of(x: float, gutters: Sequence[tuple[float, float]]) -> int:
    """Which column band ``x`` falls in; a point inside a gutter goes to the
    nearer band (the trunk's ``atribuir_coluna``: what sits on the gutter is
    the running head's middle character, and it must not be read last)."""
    for n, (a, b) in enumerate(gutters):
        if x < a:
            return n
        if x < b:
            return n if x - a <= b - x else n + 1
    return len(gutters)


def split_at_gutters(result: OcrResult,
                     gutters: Sequence[tuple[float, float]]) -> OcrResult:
    """The same reading with every line cut at the gutters.

    A line whose words all sit in one band is kept as it is (same object);
    one that crosses becomes one line per band, each boxed by its own words.
    Word order within a band is the engine's.
    """
    if not gutters:
        return result
    lines: list[OcrLine] = []
    for line in result.lines:
        groups: dict[int, list[Any]] = {}
        for word in line.words:
            groups.setdefault(_band_of(word.box.cx, gutters), []).append(word)
        if len(groups) <= 1:
            lines.append(line)
            continue
        for band in sorted(groups):
            words = tuple(groups[band])
            lines.append(replace(line, words=words, box=BBox.union_of([w.box for w in words])))
    return replace(result, lines=tuple(lines),
                   meta={**dict(result.meta), "split_at_gutters": len(gutters)})


# --------------------------------------------------------------------------- #
# The layout
# --------------------------------------------------------------------------- #


def _bands_are_prose(lines: Sequence[OcrLine], gutters: Sequence[tuple[float, float]],
                     cfg: ScanLayoutConfig) -> bool:
    """Every band reads as a column of prose, not as the White/Black bands of a move list."""
    lengths: dict[int, list[int]] = {}
    for line in lines:
        if line.words:
            lengths.setdefault(_band_of(line.box.cx, gutters), []).append(len(line.text))
    return all(_median(v) >= cfg.min_band_chars for v in lengths.values())


def _is_movetext(text: str, cfg: ScanLayoutConfig) -> bool:
    from ..lexicon import is_move_token, tokenize

    # Move numbers and their dots are the notation's own furniture, not
    # tokens that could have been moves: ``10.d4`` tokenises as three, and
    # counting the number and the dot against the move would make a column
    # of numbered moves read as one third notation.
    tokens = [t for t in tokenize(text) if not (t.isdigit() or set(t) <= set(".…"))]
    if len(tokens) < cfg.movetext_min_tokens:
        return False
    return sum(1 for t in tokens if is_move_token(t)) >= cfg.movetext_share * len(tokens)


def scan_layout(result: OcrResult, *, page_box: BBox, scale: float = 1.0,
                diagrams: Sequence[BBox] = (), page_index: int = 0,
                config: ScanLayoutConfig | None = None,
                layout_config: LayoutConfig | None = None,
                furniture: RunningFurnitureDetector | None = None) -> ScanLayout | None:
    """Lay out a page from the whole-page reading of its raster.

    ``result`` is in raster pixels; ``page_box`` and ``diagrams`` are in the
    page's own units and ``scale`` converts those to pixels (1,0 when the
    page *is* the raster).  ``None`` when the page is one column — the caller
    keeps the whole-page reading untouched — or has too few lines to say.
    """
    cfg = config or ScanLayoutConfig()
    if not cfg.enabled or not result.lines:
        return None
    gutters = find_gutters(result.lines, config=cfg)
    if not gutters or len(gutters) + 1 > cfg.max_columns:
        return None
    split = split_at_gutters(result, gutters)
    if not _bands_are_prose(split.lines, gutters, cfg):
        return None
    inv = 1.0 / scale if scale else 1.0
    lines = tuple(
        LayoutLine(box=line.box.scaled(inv), text=line.text,
                   font_size=(line.font_size or line.box.h) * inv,
                   confidence=line.confidence, source=line)
        for line in split.lines if line.text.strip()
    )
    if len(lines) < cfg.min_lines:
        return None
    layout = analyze_page(
        LayoutInput(page_box=page_box, lines=lines, diagrams=tuple(diagrams),
                    page_index=page_index),
        config=layout_config, furniture=furniture)
    if len(layout.columns) < 2 or not layout.regions:
        # The gutter did not survive the layout analyser's own vote (a
        # spanning heading, a gutter it deems too narrow at page scale):
        # two opinions that disagree are a whole page, not a column.
        return None
    regions = tuple(
        replace(region, kind=RegionKind.MOVETEXT)
        if region.kind is RegionKind.PARAGRAPH and _is_movetext(
            " ".join(lines[i].text for i in region.line_indices), cfg)
        else region
        for region in layout.regions
    )
    layout = replace(layout, regions=regions)
    movetext = sum(1 for r in regions if r.kind is RegionKind.MOVETEXT)
    notes = (f"leiaute em scan: {len(gutters) + 1} colunas achadas nas caixas de palavra "
             f"da leitura inteira ({len(split.lines)} linhas, {len(regions)} regiões"
             + (f", {movetext} de lances" if movetext else "") + ").",)
    return ScanLayout(
        layout=layout, result=split, gutters=tuple(gutters), notes=notes,
        signals={"scan_columns": len(gutters) + 1, "scan_regions": len(regions),
                 "scan_movetext_regions": movetext,
                 "scan_gutters_px": [(round(a), round(b)) for a, b in gutters]},
    )
