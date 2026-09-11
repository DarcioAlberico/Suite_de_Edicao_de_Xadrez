"""A deterministic corpus of real 800x800 board crops, for parity and timing.

The 68 annotated field pages yield ~112 diagrams -- short of the 200 the parity
gate wants -- so the harvester continues into further pages of the *same* books
with a fixed stride. Everything about the walk is deterministic: same machine,
same acervo, same crops, same order, so a parity failure is reproducible rather
than a coincidence of sampling.

Crops are the detector's own ``DiagramCandidate.board_rgb`` -- the warped 800x800
RGB the classifier actually sees in production, not a re-crop invented here.

**Crops are NOT all 800x800.** The hybrid detector has two sources: the contour
path warps to ``BOARD_SIZE`` (800), while the embedded-image path returns the
PDF's own image at whatever resolution it was stored at -- measured here at sizes
from 385x383 to 1296x1300 on the field corpus. ``split_board_into_cells`` is what
resizes them, and that resize is part of what the parity gate must cover, so the
corpus keeps the native sizes rather than normalising them away.

The cache is therefore an ``.npz`` with one array per crop plus a JSON sidecar
naming each crop's page. Delete either to force a re-harvest.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.vision.classify.cvoff import cvoff_root, ensure_cvoff_on_path  # noqa: E402

logger = logging.getLogger(__name__)

CACHE_DIR = REPO_ROOT / "benchmarks" / "corpus"
CACHE_ARRAY = CACHE_DIR / "board_crops.npz"
CACHE_INDEX = CACHE_DIR / "board_crops.json"

__all__ = ["CACHE_ARRAY", "CACHE_INDEX", "harvest_board_crops", "load_board_crops"]


def _field_pages() -> list[tuple[Path, int]]:
    root = cvoff_root()
    jsonl = root / "data" / "field_set.jsonl"
    pdf_dir = root / "PDF"
    pages: list[tuple[Path, int]] = []
    if not jsonl.is_file():
        return pages
    with jsonl.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if not record.get("reviewed"):
                continue
            path = pdf_dir / record["pdf"]
            if path.is_file():
                pages.append((path, int(record["page"])))
    return pages


def _extra_pages(seen: set[tuple[str, int]], books: list[Path], stride: int = 37) -> list[tuple[Path, int]]:
    """Further pages of the same books, deterministic stride, skipping front matter.

    Round-robin across books rather than book by book. Walking one book to
    exhaustion first would fill the whole corpus from whichever title happens to
    sort first -- "1000 Chess Problems" has over a thousand pages -- and a parity
    claim made on one book's typography is a weaker claim than the page count
    suggests.
    """
    ensure_cvoff_on_path()
    from chess_diagram_ocr.pdf_io import get_pdf_page_count  # noqa: PLC0415

    schedules: list[list[tuple[Path, int]]] = []
    for book in books:
        try:
            count = get_pdf_page_count(book)
        except Exception as exc:  # noqa: BLE001 - a broken book is skipped, not fatal
            logger.warning("Nao foi possivel abrir %s: %r", book.name, exc)
            continue
        start = min(20, max(0, count // 10))
        schedules.append(
            [(book, index) for index in range(start, count, stride) if (book.name, index) not in seen]
        )

    out: list[tuple[Path, int]] = []
    for position in range(max((len(s) for s in schedules), default=0)):
        for schedule in schedules:
            if position < len(schedule):
                out.append(schedule[position])
    return out


def harvest_board_crops(
    count: int = 220, *, max_boards: int = 12, dpi: int = 220
) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    """Detect real diagrams until ``count`` crops are collected.

    Returns:
        ``(crops, index)`` where ``crops`` is a list of RGB uint8 arrays of
        varying shape and ``index`` names the source page of each crop.
    """
    ensure_cvoff_on_path()
    from chess_diagram_ocr.detection import detect_diagrams_in_pdf_page  # noqa: PLC0415
    from chess_diagram_ocr.pdf_io import render_pdf_page  # noqa: PLC0415

    pages = _field_pages()
    seen = {(p.name, i) for p, i in pages}
    books = sorted({p for p, _ in pages}, key=lambda p: p.name)
    schedule = pages + _extra_pages(seen, books)

    crops: list[np.ndarray] = []
    index: list[dict[str, Any]] = []
    for path, page_index in schedule:
        if len(crops) >= count:
            break
        try:
            page_rgb = render_pdf_page(path, page_index, dpi=dpi)
            candidates = detect_diagrams_in_pdf_page(path, page_index, page_rgb, max_boards=max_boards)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pagina ignorada %s#%d: %r", path.name, page_index, exc)
            continue
        for order, candidate in enumerate(candidates):
            if len(crops) >= count:
                break
            board = np.ascontiguousarray(candidate.board_rgb)
            if board.ndim != 3 or board.shape[2] != 3:
                continue
            crops.append(board)
            index.append(
                {
                    "pdf": path.name,
                    "page": page_index,
                    "order": order,
                    "source": getattr(candidate, "source", ""),
                    "shape": list(board.shape),
                }
            )
    if not crops:
        raise RuntimeError("Nenhum recorte de tabuleiro foi colhido; o acervo em PDF/ esta ausente?")
    return crops, index


def load_board_crops(count: int = 220, *, refresh: bool = False) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    """Cached :func:`harvest_board_crops`."""
    if not refresh and CACHE_ARRAY.is_file() and CACHE_INDEX.is_file():
        meta = json.loads(CACHE_INDEX.read_text(encoding="utf-8"))
        if len(meta) >= count:
            with np.load(CACHE_ARRAY) as archive:
                crops = [np.ascontiguousarray(archive[f"crop_{i:05d}"]) for i in range(count)]
            return crops, meta[:count]

    crops, meta = harvest_board_crops(count)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE_ARRAY, **{f"crop_{i:05d}": crop for i, crop in enumerate(crops)})
    CACHE_INDEX.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return crops, meta


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    wanted = int(sys.argv[1]) if len(sys.argv) > 1 else 220
    array, records = load_board_crops(wanted, refresh="--refresh" in sys.argv)
    books = sorted({r["pdf"] for r in records})
    shapes = sorted({tuple(c.shape) for c in array})
    total = sum(c.nbytes for c in array)
    print(f"{len(records)} recortes de {len(books)} livros, {total / 1024**2:.1f} MiB")
    print(f"{len(shapes)} formas distintas: {shapes[:6]}{' ...' if len(shapes) > 6 else ''}")
    for book in books:
        print(f"  {sum(1 for r in records if r['pdf'] == book):4d}  {book}")
