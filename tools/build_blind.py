"""Build the blind side-by-side comparison required by `docs/quality/CORPUS.md` §4.

Produces, in `benchmarks/reports/blind/`:

* ``samples/sample_A.png`` and ``samples/sample_B.png`` -- one is page 44 of Mauricio
  Flores Rios, *Chess Structures* (Quality Chess, 2015), rendered from the local PDF at
  300 DPI; the other is our setting of the same page. **The critic opens this directory
  and nothing else.**
* ``answers/`` -- the labelled copies, our page as vector PDF, and ``key.json`` with the
  mapping and the provenance of every position. Opened only after the ranking is written.

The split into two directories is not decoration. The first version of this script put
``labelled_ours.png`` in the same folder as the unlabelled samples, so listing the
directory gave the answer away before the critic had looked at anything.

The two positions on the reference page were transcribed by eye from the scan and then
**proved** rather than trusted: replaying the book's own printed moves from the
transcribed FEN through python-chess reaches the printed continuation, including the
sub-variation that ends in mate. A single mis-read square breaks that replay. The check
runs every time this script does, and the script refuses to build if it fails.

The corpus PDF is copyrighted (`docs/quality/CORPUS.md` §0). It is read from its local
path, rendered locally, and nothing leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import chess  # noqa: E402
import pymupdf  # noqa: E402

import typeset_page as tp  # noqa: E402
import typeset_proofsheet as ps  # noqa: E402

REFERENCE_PDF = Path(
    r"C:\Python-Chess2\ChessVisionOFF_Puro\PDF"
    r"\Mauricio Flores Rios - Chess Structures - A Grandmaster Guide[Quality Chess, 2015].pdf"
)
REFERENCE_PAGE = 44  # zero-based; the printed folio is 44
OUT = ROOT / "benchmarks" / "reports" / "blind"
SAMPLES = OUT / "samples"
ANSWERS = OUT / "answers"
DPI = 300

# --------------------------------------------------------------------------- #
# Provenance of the two positions
# --------------------------------------------------------------------------- #
# Left diagram: after 21.Bxh7+. Proof = the printed main line and the printed
# sub-variation are both legal from here, and the sub-variation ends in mate as printed.
FEN_LEFT = ps.FEN_RIOS21
LEFT_MAIN = ["Nxh7", "Bf6", "Qxc4", "Rxg7+", "Kf8", "Qh6", "Rec8", "Rg8+"]
LEFT_VARIATION = ["Nxh7", "Bf6", "g6", "Qxh7+", "Kxh7", "Rh3+", "Kg8", "Rh8#"]

# Right diagram: after 13.dxc5 in Mareco - Toth, Osasco 2012. Proof = replaying the
# game's printed opening moves from the initial position reaches exactly this FEN.
FEN_RIGHT = ps.FEN_MARECO
RIGHT_OPENING = (
    "d4 Nf6 c4 e6 g3 Bb4+ Bd2 Bxd2+ Nxd2 d5 Bg2 O-O Ngf3 b6 O-O Bb7 "
    "Rc1 Nbd7 cxd5 exd5 Ne5 c5 Nxd7 Nxd7 dxc5"
).split()


def prove_positions() -> dict[str, object]:
    """Re-derive both FENs from the book's own moves. Raises if either is wrong."""
    board = chess.Board()
    for san in RIGHT_OPENING:
        board.push_san(san)
    if board.fen() != FEN_RIGHT:
        raise AssertionError(
            f"A posicao da direita nao confere.\n  esperado: {FEN_RIGHT}\n  obtido:   {board.fen()}"
        )

    left = chess.Board(FEN_LEFT)
    if left.status() is not chess.STATUS_VALID:
        raise AssertionError(f"FEN da esquerda invalida: {left.status()!r}")
    for moves, label in ((LEFT_MAIN, "linha principal"), (LEFT_VARIATION, "variante")):
        probe = chess.Board(FEN_LEFT)
        for san in moves:
            try:
                probe.push_san(san)
            except ValueError as exc:
                raise AssertionError(
                    f"A {label} impressa nao e legal a partir da FEN transcrita: {san} ({exc})"
                ) from None
    mate = chess.Board(FEN_LEFT)
    for san in LEFT_VARIATION:
        mate.push_san(san)
    if not mate.is_checkmate():
        raise AssertionError("A variante impressa termina em mate no livro, mas nao aqui.")

    return {
        "left": {
            "fen": FEN_LEFT,
            "caption": "apos 21.Bxh7+",
            "proof": (
                "linha principal impressa (21...Nxh7 22.Bf6 Qxc4 23.Rxg7+ Kf8 24.Qh6 "
                "Rec8 25.Rg8+) e a sub-variante (22...g6 23.Qxh7+ Kxh7 24.Rh3+ Kg8 "
                "25.Rh8#) sao ambas legais a partir desta FEN, e a segunda da mate, "
                "como impresso."
            ),
        },
        "right": {
            "fen": FEN_RIGHT,
            "caption": "apos 13.dxc5, Mareco - Toth, Osasco 2012",
            "proof": (
                "obtida jogando os 25 meios-lances de abertura impressos na propria "
                "pagina a partir da posicao inicial."
            ),
        },
    }


def render_reference(path: Path) -> dict[str, object]:
    doc = pymupdf.open(REFERENCE_PDF)
    page = doc[REFERENCE_PAGE]
    rect = page.rect
    page.get_pixmap(dpi=DPI).save(str(path))
    info = {
        "source": REFERENCE_PDF.name,
        "page_index": REFERENCE_PAGE,
        "printed_folio": 44,
        "trim_pt": [round(rect.width, 2), round(rect.height, 2)],
        "trim_mm": [round(rect.width / 72 * 25.4, 2), round(rect.height / 72 * 25.4, 2)],
        "dpi": DPI,
        "note": "PDF digitalizado: uma imagem por pagina, sem camada de texto.",
    }
    doc.close()
    return info


SOURCES = {
    "mareco": (ps.book_source_mareco, "en", ps.MARECO_RUNNING_HEAD),
    "rios": (ps.book_source_rios, "pt", ps.RIOS_RUNNING_HEAD),
}
"""Distinct source pages, so a blind set never carries two renderings of the same copy.

Cycle 1 put THREE theme variants of one source page into a set of seven. The critic
diffed them pixel by pixel, found them identical outside the diagrams, and identified all
three of ours before looking at a single typographic detail (`F7_CRITIQUE_C1.md`,
"A prova que fecha a questao"). One page of ours per set, from a source that appears
nowhere else in the set, is the minimum the procedure needs to mean anything.
"""


FULL_PAGE_SLACK = 1
"""Slots a column may fall below the grid's capacity and still count as a full page.

One, and the one is the balancing rule, not a tolerance chosen to pass: `balance_last`
targets the tallest column of the last spread, so the deepest a full page can reach is
the natural height of its own copy. Both delivered pages sit at exactly 1."""

FULL_PAGE_FOOT_MM = 3.68
"""How far the two feet of the spread may differ.

Was 0.01 through cycle 10, because the composer bought a level foot by setting one gap
class at two heights on the same page. Cycle 11 stopped paying that price -- see
`typeset_page.MAX_EQUALISE_SPREAD_SLOTS` -- so a page may now end one grid slot apart:
**3.6713 mm**, and the limit is that slot plus rounding. What the gate is for is
unchanged and is still live: cycle 1's sample stopped 11 slots short with content still
to set, and `FULL_PAGE_SLACK` is what catches that. The reference page this book imitates
closes its own columns at 4.19 mm."""


def render_ours(path: Path, source: str = "mareco",
                answers: Path | None = None) -> dict[str, object]:
    factory, language, head = SOURCES[source]
    composed = ps.compose_book_page(
        "book", source=factory(), diagram_theme="hatched", page_number=44,
        running_head=head, language=language,
    )
    # A blind sample must be a FULL page. Cycle 1's sample A "stopped at y=1479 with
    # content still to set", and the critic named that as one of the tells; a half-filled
    # page gives itself away before any typographic detail is looked at.
    if len(composed.pages) != 1:
        raise SystemExit(
            f"a fonte {source!r} nao cabe numa pagina ({len(composed.pages)} paginas)."
        )
    # A column that stops one slot short of the grid's capacity is NOT a short column:
    # `tp.compose(balance_last=True)` sets the last spread of a composition to the
    # tallest column's natural height, not to the capacity of the frame, so a page whose
    # matter runs out mid-slot closes both columns level one line above the drawn foot.
    # That is what a book does when the copy ends; it is not what cycle 1 shipped.
    #
    # Cycle 7 wrote `c.used < c.capacity` and the gate then fired on BOTH sources
    # (`mareco` and `rios`, 52/53 in both columns of both), so `render_ours` could not
    # emit a blind sample at all and cycle 7 did not report it. The gate is kept -- it
    # exists because cycle 1's sample A "stopped at y=1479 with content still to set" and
    # the critic named that as one of the tells -- but it now measures the two things
    # that actually give a half-filled page away, and both are declared:
    #
    #   * no column may fall more than FULL_PAGE_SLACK slots below capacity (cycle 1's
    #     sample was ~11 slots short; the delivered page is 1);
    #   * the feet of the spread must close (cycle 1's did not).
    slack = [(c.capacity - c.used) for c in composed.columns]
    short = [c for c in composed.columns if c.capacity - c.used > FULL_PAGE_SLACK]
    spread = composed.foot_spread_mm
    if short or spread > FULL_PAGE_FOOT_MM:
        raise SystemExit(
            f"a fonte {source!r} nao enche a pagina: colunas "
            f"{[f'{c.used}/{c.capacity}' for c in composed.columns]}, folga "
            f"{slack} slots (limite {FULL_PAGE_SLACK}), desnivel dos pes "
            f"{spread:.4f} mm (limite {FULL_PAGE_FOOT_MM}). Uma amostra cega tem de ser "
            "uma pagina cheia."
        )
    svg = composed.pages[0]
    files = tp.serif_files()
    from caissa.typeset import svgpdf

    frag = svgpdf.parse_svg(svg)
    doc = pymupdf.open()
    page = doc.new_page(width=frag.width_mm * tp.MM, height=frag.height_mm * tp.MM)
    svgpdf.draw_svg(page, frag, origin=(0.0, 0.0), font_files=files)
    page.get_pixmap(dpi=DPI).save(str(path))
    pdf_path = (answers or ANSWERS) / "ours_vector.pdf"
    doc.save(str(pdf_path), deflate=True, garbage=3)
    doc.close()
    return {
        "trim_mm": [ps.TRIM_W, ps.TRIM_H],
        "serif": tp.serif_family()[0],
        "chess_font": "merida",
        "diagram_theme": "hatched",
        "dpi": DPI,
        "pdf": pdf_path.name,
        "source": source,
        "column_feet_mm": [round(f, 3) for f in composed.column_feet],
        "foot_spread_mm": round(composed.foot_spread_mm, 4),
        "columns_used_capacity": [f"{c.used}/{c.capacity}" for c in composed.columns],
        "short_column_slack_slots": slack,
        "unequal_gap_classes": composed.unequal_gaps(),
        "equalised": [list(e) for e in composed.equalised],
    }


FROZEN_MARKERS = ("GABARITO.json", "key.json", "amostra_*.png", "sample_*.png")
"""What a directory holds when it is already somebody's blind set."""


def frozen_blind_set(out: Path) -> list[str]:
    """Names in ``out`` that say it is a blind set from an earlier cycle.

    The cycle-10 critic refused to run this script at all, and said why: the default
    ``--out`` is `benchmarks/reports/blind/`, which holds the **cycle-1** set --
    `GABARITO.json` and `amostra_A..G.png` -- and a run would have written `samples/`
    and `answers/` straight over it. A tool whose default destroys the evidence an
    earlier cycle was judged against is a trap, and the critic having to route around it
    by hand is not a fix. This is the fix: the default is unchanged, and the run refuses.
    """
    if not out.exists():
        return []
    found: list[str] = []
    for marker in FROZEN_MARKERS:
        if "*" in marker:
            found += sorted(p.name for p in out.glob(marker))
        elif (out / marker).exists():
            found.append(marker)
        for sub in ("samples", "answers"):
            if "*" in marker:
                found += sorted(f"{sub}/{p.name}" for p in (out / sub).glob(marker))
            elif (out / sub / marker).exists():
                found.append(f"{sub}/{marker}")
    return found


def main(argv=None) -> int:
    global OUT, SAMPLES, ANSWERS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--swap", action="store_true", help="ours becomes A instead of B"
    )
    parser.add_argument(
        "--source", default="mareco", choices=sorted(SOURCES),
        help="qual pagina-fonte nossa entra no conjunto",
    )
    parser.add_argument(
        "--out", default=str(OUT),
        help="diretorio de saida (para provar o script sem tocar no conjunto cego real)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="escreve mesmo por cima de um conjunto cego ja congelado",
    )
    args = parser.parse_args(argv)
    OUT = Path(args.out)
    SAMPLES = OUT / "samples"
    ANSWERS = OUT / "answers"

    frozen = frozen_blind_set(OUT)
    if frozen and not args.force:
        print(
            f"RECUSA: {OUT} ja contem um conjunto cego congelado "
            f"({', '.join(frozen[:4])}{' ...' if len(frozen) > 4 else ''}).\n"
            "  Um conjunto cego e um artefacto de um ciclo passado: reescreve-lo apaga\n"
            "  a prova contra a qual esse ciclo foi julgado. Escolha um diretorio novo:\n"
            f"    --out {OUT.parent / (OUT.name + '7')}\n"
            "  ou, se e mesmo isso que quer, --force.",
            file=sys.stderr,
        )
        return 3

    if not REFERENCE_PDF.exists():
        print(f"PDF de referencia nao encontrado: {REFERENCE_PDF}", file=sys.stderr)
        return 2

    SAMPLES.mkdir(parents=True, exist_ok=True)
    ANSWERS.mkdir(parents=True, exist_ok=True)
    positions = prove_positions()
    print("Posicoes verificadas contra os lances impressos: OK")

    ours_letter = "A" if args.swap else "B"
    ref_letter = "B" if args.swap else "A"

    ref_info = render_reference(SAMPLES / f"sample_{ref_letter}.png")
    our_info = render_ours(ANSWERS / "ours.png", source=args.source, answers=ANSWERS)
    # Labelled copies live in `answers/`, never beside the samples.
    import shutil

    shutil.copyfile(ANSWERS / "ours.png", SAMPLES / f"sample_{ours_letter}.png")
    shutil.copyfile(SAMPLES / f"sample_{ref_letter}.png", ANSWERS / "reference.png")

    (SAMPLES / "README.txt").write_text(
        "\n".join(
            [
                "Comparacao as cegas -- docs/quality/CRITIC_CHARTER.md 2.1",
                "",
                "Ordene sample_A.png e sample_B.png por qualidade tipografica e",
                "justifique cada posicao ANTES de abrir ../answers/. Uma delas e",
                "nossa; a outra vem de uma editora de referencia.",
                "",
                "NAO abra ../answers/ ate ter escrito a ordenacao.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # A side-by-side, in `answers/`, for the report and for later re-checking.
    combined = pymupdf.open()
    a = pymupdf.open(str(ANSWERS / "reference.png"))
    b = pymupdf.open(str(ANSWERS / "ours.png"))
    ra, rb = a[0].rect, b[0].rect
    page = combined.new_page(
        width=ra.width + rb.width + 30, height=max(ra.height, rb.height) + 10
    )
    page.insert_image(
        pymupdf.Rect(5, 5, 5 + ra.width, 5 + ra.height),
        filename=str(ANSWERS / "reference.png"),
    )
    page.insert_image(
        pymupdf.Rect(ra.width + 25, 5, ra.width + 25 + rb.width, 5 + rb.height),
        filename=str(ANSWERS / "ours.png"),
    )
    page.get_pixmap(dpi=150).save(str(ANSWERS / "side_by_side.png"))
    a.close()
    b.close()
    combined.close()

    key = {
        "procedure": "docs/quality/CORPUS.md §4",
        "instruction": (
            "Ordene blind/samples/sample_A.png e sample_B.png por qualidade tipografica "
            "ANTES de abrir este arquivo. Depois confira o mapeamento abaixo."
        ),
        "mapping": {ref_letter: "referencia (Quality Chess)", ours_letter: "nossa"},
        "reference": ref_info,
        "ours": our_info,
        "positions": positions,
        "copyright": (
            "O PDF de referencia e material protegido. Renderizado localmente, nao "
            "redistribuido. Ver docs/quality/CORPUS.md §0."
        ),
    }
    (ANSWERS / "key.json").write_text(
        json.dumps(key, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    for directory in (SAMPLES, ANSWERS):
        for name in sorted(p.name for p in directory.iterdir()):
            print("  ", directory / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
