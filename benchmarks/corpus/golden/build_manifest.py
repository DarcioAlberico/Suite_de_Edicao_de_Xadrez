"""Build the golden manifest (Sol §SOL-0) from the truth the repository holds.

Sources, in order:

1. ``derived/llm_ocr_regions.jsonl`` -- regions of born-digital PDFs whose ink
   and text layer were verified to agree (see ``build_ocr_regions.py``).
   Rendered from the PDF; measured under the native stratum and three
   synthetic degradations.
2. ``derived/llm_ocr_synth.jsonl`` -- paragraphs of born-digital books,
   typeset by the benchmark in an ordinary text font.
3. ``authored.json`` -- paragraphs written for this corpus in German,
   Spanish, Russian, Portuguese and English, with the piece letters of each
   language.  The only source of Spanish and Cyrillic truth in the corpus.
4. Composites typeset by the benchmark from 2 and 3: two-column pages (the
   reading-order stratum), game-index tables and problem pages with an
   empty board and a label.
5. Negative controls: blank, board, stains, border, noise, photo.

Every item's partition is fixed by hash of its id (``caissa.ocr.golden``);
this script never assigns one.  Run::

    python benchmarks/corpus/golden/build_manifest.py

Two files come out.  ``manifest.json`` is **versioned** and holds only text
the repository may carry: the authored paragraphs, the composites built
from them, and the controls.  ``manifest.private.json`` adds the items whose
truth is a passage of a copyrighted book (sources 1 and 2); it stays on this
machine, like ``derived/`` and the PDFs (docs/quality/CORPUS.md), and the
benchmark prefers it when present.  A report records which one it measured
by the manifest's content hash.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.ocr.golden import (  # noqa: E402
    ControlKind,
    GoldenItem,
    GoldenManifest,
    GoldenRegion,
    Partition,
    Source,
    annotate_moves,
    save_manifest,
)
from caissa.ocr.metrics import move_tokens  # noqa: E402

DERIVED = HERE.parent / "derived"
MANIFEST = HERE / "manifest.json"
PRIVATE_MANIFEST = HERE / "manifest.private.json"
CORPUS_VERSION = "2026.09.13"

#: Text fonts for the synthetic strata, cycled by row.  All serif but one, as
#: chess books are.  ``times.ttf`` also covers Cyrillic.
SYNTH_FONTS = ("times.ttf", "BOOKOS.TTF", "georgia.ttf", "constan.ttf", "calibri.ttf")
PDF_STRATA = ("native", "scan_clean_300", "scan_degraded_150", "shadow_curl_bleed")
SYNTH_STRATA = ("scan_clean_300", "scan_degraded_150", "shadow_curl_bleed", "fax_dither", "photo")
SCRIPT_OF = {"ru": "cyrillic"}
MOVETEXT_MIN_MOVES = 6


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _genre(text: str) -> str:
    n = len(move_tokens(text))
    if n >= MOVETEXT_MIN_MOVES:
        return "movetext"
    return "mixed" if n else "prose"


def _region(text: str, kind: str, lang: str, order: int = 0) -> GoldenRegion:
    return annotate_moves(GoldenRegion(
        kind=kind, truth=text, reading_order=order, prose_lang=lang, notation_lang=lang))


def real_items() -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for row in _read_jsonl(DERIVED / "llm_ocr_regions.jsonl"):
        lang = row["lang"]
        genre = _genre(row["truth"])
        items.append(GoldenItem(
            id=f"real:{row['book'][:24]}:{row['page_index']}:{round(row['clip'][1])}",
            source=Source.PDF_NATIVE,
            book=row["book"],
            page_index=int(row["page_index"]),
            clip=tuple(float(v) for v in row["clip"]),
            prose_lang=lang, notation_lang=lang,
            script=SCRIPT_OF.get(lang, "latin"),
            genre=genre,
            regions=(_region(row["truth"], "movetext" if genre == "movetext" else "paragraph",
                             lang),),
            strata=PDF_STRATA,
            tags=("verified-ink",),
            notes="verdade conferida contra a tinta (build_ocr_regions.py)",
        ))
    return items


def synth_items() -> tuple[list[GoldenItem], list[dict]]:
    """Paragraphs of born-digital books, typeset by the benchmark (private)."""
    rows = _read_jsonl(DERIVED / "llm_ocr_synth.jsonl")
    items: list[GoldenItem] = []
    pool: list[dict] = []
    for index, row in enumerate(rows):
        lang = row["lang"]
        font = SYNTH_FONTS[index % len(SYNTH_FONTS)]
        genre = _genre(row["text"])
        items.append(GoldenItem(
            id=f"synth:{row['book'][:24]}:{row['page_index']}:{index}",
            source=Source.SYNTH, book=row["book"], page_index=int(row["page_index"]),
            synth_font=font, prose_lang=lang, notation_lang=lang,
            script=SCRIPT_OF.get(lang, "latin"), genre=genre,
            regions=(_region(row["text"], "movetext" if genre == "movetext" else "paragraph",
                             lang),),
            strata=SYNTH_STRATA,
            tags=("synthetic",),
        ))
        pool.append({"text": row["text"], "lang": lang})
    return items, pool


def authored_items() -> tuple[list[GoldenItem], list[dict]]:
    """Paragraphs written for this corpus (public)."""
    with (HERE / "authored.json").open(encoding="utf-8") as handle:
        authored = json.load(handle)["items"]
    items: list[GoldenItem] = []
    pool: list[dict] = []
    for index, row in enumerate(authored):
        lang = row["lang"]
        font = SYNTH_FONTS[(index + 2) % len(SYNTH_FONTS)]
        genre = _genre(row["text"])
        items.append(GoldenItem(
            id=f"authored:{lang}:{index}",
            source=Source.SYNTH, book="authored", page_index=index,
            synth_font=font, prose_lang=lang, notation_lang=row.get("notation", lang),
            script=SCRIPT_OF.get(lang, "latin"), genre=genre,
            regions=(_region(row["text"], "movetext" if genre == "movetext" else "paragraph",
                             lang),),
            strata=SYNTH_STRATA,
            tags=("synthetic", "authored"),
        ))
        pool.append({"text": row["text"], "lang": lang})
    return items, pool


def two_column_items(pool: list[dict], tag: str) -> list[GoldenItem]:
    """Pairs of paragraphs set side by side: the reading-order stratum."""
    items: list[GoldenItem] = []
    same_lang = sorted(pool, key=lambda p: p["lang"])
    for k in range(0, min(40, len(same_lang) - 1), 2):
        left, right = same_lang[k], same_lang[k + 1]
        lang = left["lang"] if left["lang"] == right["lang"] else "mixed"
        items.append(GoldenItem(
            id=f"twocol:{tag}:{k // 2}",
            source=Source.SYNTH, book="composite", page_index=k // 2,
            synth_font=SYNTH_FONTS[(k // 2) % len(SYNTH_FONTS)],
            prose_lang=lang, notation_lang=lang, layout="two-column", columns=2,
            genre="mixed",
            regions=(_region(left["text"], "paragraph", left["lang"], 0),
                     _region(right["text"], "paragraph", right["lang"], 1)),
            strata=("scan_clean_300", "scan_degraded_150"),
            tags=("synthetic", "reading-order"),
        ))
    return items


_TABLE_ROWS = [
    ("Kasparov – Karpov", "Moscovo 1985", "Siciliana, Scheveningen", "47"),
    ("Fischer – Spassky", "Reykjavik 1972", "Nimzo-Índia", "112"),
    ("Capablanca – Marshall", "Nova Iorque 1918", "Ruy López", "9"),
    ("Tal – Botvinnik", "Moscovo 1960", "Francesa, Winawer", "203"),
    ("Anand – Kramnik", "Bona 2008", "Gambito da Dama Recusado", "88"),
    ("Carlsen – Nakamura", "Wijk aan Zee 2011", "Índia do Rei", "301"),
    ("Steinitz – Zukertort", "St. Louis 1886", "Abertura Escocesa", "15"),
    ("Lasker – Rubinstein", "São Petersburgo 1914", "Espanhola", "56"),
    ("Alekhine – Euwe", "Haia 1937", "Eslava", "140"),
    ("Petrosian – Spassky", "Moscovo 1966", "Inglesa", "77"),
    ("Karpov – Korchnoi", "Baguio 1978", "Espanhola, Aberta", "230"),
    ("Kramnik – Leko", "Brissago 2004", "Petroff", "184"),
]


def table_items() -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for k in range(8):
        rows = [_TABLE_ROWS[(k + i) % len(_TABLE_ROWS)] for i in range(5)]
        text = "\n".join(f"{k * 5 + i + 1}. {a}  {b}  {c}  {d}" for i, (a, b, c, d) in enumerate(rows))
        items.append(GoldenItem(
            id=f"table:{k}", source=Source.SYNTH, book="composite", page_index=k,
            synth_font=SYNTH_FONTS[k % len(SYNTH_FONTS)],
            prose_lang="pt", notation_lang="", layout="table", genre="table",
            regions=(GoldenRegion(kind="table", truth=text, reading_order=0, prose_lang="pt"),),
            strata=("scan_clean_300", "scan_degraded_150"),
            tags=("synthetic", "table"),
        ))
    return items


_PROBLEMS = [
    ("Nº 12 — Brancas jogam e ganham", "1.Txf7! Rxf7 2.Dh5+ Rg8 3.Bc4+ Rh8 4.Dxh7#", "pt"),
    ("No. 7 — White to play and mate in three", "1.Qg8+! Rxg8 2.Nf7+ Kh7 3.Nxd8", "en"),
    ("Nr. 23 — Weiß zieht und gewinnt", "1.Dxh7+! Kxh7 2.Th3+ Kg8 3.Th8#", "de"),
    ("Nº 31 — Juegan las blancas y ganan", "1.Cf6+! gxf6 2.Dg4+ Rh8 3.Dg7#", "es"),
    ("№ 44 — Белые начинают и выигрывают", "1.Фxh7+! Крxh7 2.Лh3+ Крg8 3.Лh8#", "ru"),
    ("Nº 58 — Pretas jogam e empatam", "1...Th1+! 2.Rxh1 Df1+ 3.Rh2 Dh3+ 4.Rg1 Dg3+", "pt"),
    ("No. 61 — Black to play and win", "1...Bxh2+! 2.Kxh2 Qh4+ 3.Kg1 Ng4 4.Re1 Qh2#", "en"),
    ("Nr. 75 — Matt in zwei Zügen", "1.Sd5! Kxd5 2.Dd4#", "de"),
]


def problem_items() -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for k, (label, solution, lang) in enumerate(_PROBLEMS):
        items.append(GoldenItem(
            id=f"problem:{k}", source=Source.SYNTH, book="composite", page_index=k,
            synth_font=SYNTH_FONTS[(k + 1) % len(SYNTH_FONTS)],
            prose_lang=lang, notation_lang=lang, layout="problems", genre="problems",
            script=SCRIPT_OF.get(lang, "latin"),
            regions=(GoldenRegion(kind="diagram_label", truth=label, reading_order=0,
                                  prose_lang=lang),
                     _region(solution, "movetext", lang, 1)),
            strata=("scan_clean_300", "scan_degraded_150"),
            tags=("synthetic", "problems", "board-without-prose"),
        ))
    return items


def control_items() -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for kind in ControlKind:
        for seed in (1, 2):
            items.append(GoldenItem(
                id=f"control:{kind}:{seed}", source=Source.CONTROL, control=kind,
                page_index=seed, genre="control", quality="control", layout="none",
                strata=("native",), tags=("negative-control",),
                notes="a resposta certa é abster-se",
            ))
    return items


def _write(items: list[GoldenItem], path: Path, private: bool) -> GoldenManifest | None:
    manifest = GoldenManifest(
        items=items, corpus_version=CORPUS_VERSION,
        built_at=datetime.now(UTC).isoformat(timespec="seconds"),
        notes=[
            ("Manifesto privado: inclui passagens de livros do acervo; não sai desta máquina."
             if private else
             "Manifesto público: só texto que o repositório pode carregar (autoral, "
             "compostos e controles)."),
            "Itens de PDF são regiões (não páginas inteiras) de livros nativos com verdade "
            "conferida contra a tinta; a imagem é renderizada do PDF em tempo de medição.",
            "Itens sintéticos são tipografados pelo benchmark a partir do texto; "
            "não são digitalizações reais e o relatório nomeia o estrato em todo número.",
            "Ainda não há 200 páginas inteiras rotuladas por humanos: este manifesto é o "
            "esqueleto medível, e o rótulo humano entra por item sem mudar o esquema.",
        ],
    )
    problems = manifest.validate()
    if problems:
        for problem in problems:
            print("!", problem)
        return None
    save_manifest(manifest, path)
    parts = {str(p): len(manifest.by_partition(p)) for p in Partition}
    print(f"{len(items)} itens -> {path}")
    print("  partições:", parts)
    for facet in ("source", "prose_lang", "script", "layout", "genre"):
        print(f"  {facet}: {manifest.facet_counts(facet)}")
    print("  hash:", manifest.content_hash())
    return manifest


def main() -> int:
    authored, authored_pool = authored_items()
    public = (authored + two_column_items(authored_pool, "a") + table_items()
              + problem_items() + control_items())
    if _write(public, MANIFEST, private=False) is None:
        return 1
    real = real_items()
    synth, derived_pool = synth_items()
    private = public + real + synth + two_column_items(derived_pool, "d")
    if not real and not synth:
        print("sem material derivado nesta máquina: manifesto privado não escrito")
        return 0
    return 0 if _write(private, PRIVATE_MANIFEST, private=True) is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
