"""The golden corpus manifest — Sol §SOL-0.

A benchmark that cannot say *which page, which region, which stratum* a
number came from is a rumour.  This module is the schema that makes the
number traceable: every item names its source (a PDF page and clip, a
synthetic paragraph, or a negative control), the facets it is stratified by,
the truth per region in reading order, the move tokens the truth contains,
and the partition it belongs to.

Three rules are enforced here rather than left to discipline:

**Partitions are fixed by hash, not by hand.**  An item's partition is a
deterministic function of its identifier, so adding items never moves an
existing one between development, calibration and blind test, and nobody
can "just this once" pull a hard blind page into calibration.

**The blind partition is not readable by default.**  :func:`load_manifest`
hides it unless the caller asks with ``include_blind=True``, and the
benchmark refuses to fit anything on it.  The review model (SOL-11) uses
the same flag to keep human corrections on blind pages out of calibration.

**Truth is text the repository is allowed to hold.**  The corpus PDFs are
copyrighted and never leave the machine (docs/quality/CORPUS.md); an item
carries a few hundred characters of truth and a clip rectangle, and the
image is rendered from the PDF at benchmark time.  Synthetic items carry the
text they are typeset from; controls carry no text at all.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .metrics import move_tokens, normalise

__all__ = [
    "DEGRADATIONS",
    "MANIFEST_VERSION",
    "ControlKind",
    "Degradation",
    "GoldenItem",
    "GoldenManifest",
    "GoldenRegion",
    "Partition",
    "Source",
    "load_manifest",
    "partition_for",
    "save_manifest",
]

MANIFEST_VERSION = 1

#: Development / calibration / blind shares, in that order.
PARTITION_SHARES: tuple[float, float, float] = (0.50, 0.25, 0.25)


class Partition(StrEnum):
    DEV = "dev"
    CALIB = "calib"
    BLIND = "blind"


class Source(StrEnum):
    """Where the pixels come from."""

    PDF_NATIVE = "pdf-native"        # born-digital, rendered from the PDF
    PDF_SCAN = "pdf-scan"            # a scanned PDF (image-only layer)
    SYNTH = "synth"                  # typeset here from truth text
    CONTROL = "control"              # negative control, no text by design


class ControlKind(StrEnum):
    BLANK = "blank"
    BOARD = "board"                  # an empty chess board, no prose
    STAINS = "stains"
    BORDER = "border"
    NOISE = "noise"
    PHOTO = "photo"                  # a smooth photograph-like gradient


@dataclass(frozen=True, slots=True)
class Degradation:
    """How a clean render is turned into the stratum's scan.

    ``dpi`` is the *effective* resolution of the resulting image; the
    benchmark renders at 300 and resamples, so the number is exact.
    """

    name: str
    dpi: int
    blur: float = 0.0
    noise: float = 0.0
    angle: float = 0.0
    jpeg: int = 95
    fade: float = 0.0
    shadow: float = 0.0
    bleed: float = 0.0
    curl: float = 0.0
    dither: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


#: The strata SOL-0 lists, as degradations of a 300 DPI render.  Names are
#: stable identifiers: the report is keyed by them.
DEGRADATIONS: dict[str, Degradation] = {
    "native": Degradation("native", dpi=300),
    "scan_clean_300": Degradation("scan_clean_300", dpi=300, blur=0.4, noise=4, jpeg=80),
    "scan_degraded_150": Degradation(
        "scan_degraded_150", dpi=150, blur=0.9, noise=12, angle=0.6, jpeg=45, fade=0.15),
    "shadow_curl_bleed": Degradation(
        "shadow_curl_bleed", dpi=200, blur=0.5, noise=8, angle=0.4, jpeg=60,
        shadow=0.35, bleed=0.25, curl=0.6),
    "fax_dither": Degradation("fax_dither", dpi=200, blur=0.6, noise=6, jpeg=70, dither=True),
    "photo": Degradation(
        "photo", dpi=180, blur=0.8, noise=10, angle=1.5, jpeg=55, shadow=0.45, curl=1.0),
}


@dataclass(frozen=True, slots=True)
class GoldenRegion:
    """One labelled region of an item, in reading order."""

    kind: str                          # RegionKind value: paragraph, movetext, ...
    truth: str
    box: tuple[float, float, float, float] | None = None   # points, when known
    reading_order: int = 0
    prose_lang: str = ""
    notation_lang: str = ""
    #: Move tokens of the truth, in order.  Auto-annotated unless ``moves_verified``.
    moves: tuple[str, ...] = ()
    moves_verified: bool = False
    #: Identifier of the game/diagram the movetext belongs to, when labelled.
    game_ref: str | None = None
    diagram_ref: str | None = None
    #: FEN before the first move of a movetext region, when labelled.
    start_fen: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["moves"] = list(self.moves)
        return data


@dataclass(frozen=True, slots=True)
class GoldenItem:
    """One page or page fragment with everything needed to render and score it."""

    id: str
    source: Source
    book: str = ""
    page_index: int = -1
    clip: tuple[float, float, float, float] | None = None
    #: Synthetic items: the typeset text and the font; controls: the kind.
    synth_font: str = ""
    control: ControlKind | None = None
    #: Facets.  Free strings on purpose: the benchmark groups by them.
    prose_lang: str = ""
    notation_lang: str = ""
    notation_style: str = "algebraic"      # algebraic | figurine | descriptive | historical
    script: str = "latin"
    layout: str = "single"                 # single | two-column | table | index | problems
    columns: int = 1
    genre: str = "prose"                   # prose | movetext | problems | table | mixed
    quality: str = "clean"                 # clean | damaged-font | degraded | ...
    damage: str = ""                       # what is wrong with the source layer, if anything
    regions: tuple[GoldenRegion, ...] = ()
    #: Degradations (keys of :data:`DEGRADATIONS`) this item is measured under.
    strata: tuple[str, ...] = ("native",)
    tags: tuple[str, ...] = ()
    notes: str = ""

    @property
    def truth(self) -> str:
        """Every region's truth in reading order, one region per paragraph."""
        return "\n".join(r.truth for r in sorted(self.regions, key=lambda r: r.reading_order))

    @property
    def partition(self) -> Partition:
        return partition_for(self.id)

    @property
    def is_control(self) -> bool:
        return self.source is Source.CONTROL

    @property
    def moves(self) -> tuple[str, ...]:
        return tuple(m for r in self.regions for m in r.moves)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": str(self.source),
            "book": self.book,
            "page_index": self.page_index,
            "clip": list(self.clip) if self.clip else None,
            "synth_font": self.synth_font,
            "control": str(self.control) if self.control else None,
            "prose_lang": self.prose_lang,
            "notation_lang": self.notation_lang,
            "notation_style": self.notation_style,
            "script": self.script,
            "layout": self.layout,
            "columns": self.columns,
            "genre": self.genre,
            "quality": self.quality,
            "damage": self.damage,
            "regions": [r.as_dict() for r in self.regions],
            "strata": list(self.strata),
            "tags": list(self.tags),
            "notes": self.notes,
            "partition": str(self.partition),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GoldenItem:
        regions = tuple(
            GoldenRegion(
                kind=str(r.get("kind", "paragraph")),
                truth=str(r.get("truth", "")),
                box=tuple(r["box"]) if r.get("box") else None,   # type: ignore[arg-type]
                reading_order=int(r.get("reading_order", i)),
                prose_lang=str(r.get("prose_lang", "")),
                notation_lang=str(r.get("notation_lang", "")),
                moves=tuple(r.get("moves", ())),
                moves_verified=bool(r.get("moves_verified", False)),
                game_ref=r.get("game_ref"),
                diagram_ref=r.get("diagram_ref"),
                start_fen=r.get("start_fen"),
            )
            for i, r in enumerate(data.get("regions", ()))
        )
        item = cls(
            id=str(data["id"]),
            source=Source(data.get("source", "pdf-native")),
            book=str(data.get("book", "")),
            page_index=int(data.get("page_index", -1)),
            clip=tuple(data["clip"]) if data.get("clip") else None,   # type: ignore[arg-type]
            synth_font=str(data.get("synth_font", "")),
            control=ControlKind(data["control"]) if data.get("control") else None,
            prose_lang=str(data.get("prose_lang", "")),
            notation_lang=str(data.get("notation_lang", "")),
            notation_style=str(data.get("notation_style", "algebraic")),
            script=str(data.get("script", "latin")),
            layout=str(data.get("layout", "single")),
            columns=int(data.get("columns", 1)),
            genre=str(data.get("genre", "prose")),
            quality=str(data.get("quality", "clean")),
            damage=str(data.get("damage", "")),
            regions=regions,
            strata=tuple(data.get("strata", ("native",))),
            tags=tuple(data.get("tags", ())),
            notes=str(data.get("notes", "")),
        )
        recorded = data.get("partition")
        if recorded is not None and str(recorded) != str(item.partition):
            raise ValueError(
                f"item {item.id}: partição registrada '{recorded}' difere da "
                f"partição fixa '{item.partition}' — o manifesto foi editado à mão")
        return item


def partition_for(item_id: str) -> Partition:
    """Fixed partition of an item: a hash of its id against the shares."""
    digest = hashlib.sha256(item_id.encode("utf-8")).digest()
    fraction = int.from_bytes(digest[:8], "big") / float(1 << 64)
    dev, calib, _ = PARTITION_SHARES
    if fraction < dev:
        return Partition.DEV
    if fraction < dev + calib:
        return Partition.CALIB
    return Partition.BLIND


def annotate_moves(region: GoldenRegion) -> GoldenRegion:
    """Fill ``moves`` from the truth when it has not been verified by hand."""
    if region.moves_verified and region.moves:
        return region
    return GoldenRegion(
        kind=region.kind, truth=region.truth, box=region.box,
        reading_order=region.reading_order, prose_lang=region.prose_lang,
        notation_lang=region.notation_lang,
        moves=tuple(move_tokens(region.truth)), moves_verified=False,
        game_ref=region.game_ref, diagram_ref=region.diagram_ref,
        start_fen=region.start_fen,
    )


@dataclass(slots=True)
class GoldenManifest:
    """The whole corpus plus its identity."""

    items: list[GoldenItem] = field(default_factory=list)
    version: int = MANIFEST_VERSION
    corpus_version: str = "0"
    built_at: str = ""
    notes: list[str] = field(default_factory=list)
    strata: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {k: v.as_dict() for k, v in DEGRADATIONS.items()})

    def __iter__(self) -> Iterator[GoldenItem]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def by_partition(self, partition: Partition) -> list[GoldenItem]:
        return [i for i in self.items if i.partition is partition]

    def controls(self) -> list[GoldenItem]:
        return [i for i in self.items if i.is_control]

    def facet_counts(self, facet: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            key = str(getattr(item, facet, ""))
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def content_hash(self) -> str:
        """Hash of every item — the corpus identity a report records."""
        payload = json.dumps([i.as_dict() for i in self.items], sort_keys=True,
                             ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    def validate(self) -> list[str]:
        """Problems that make the manifest unfit for measurement."""
        problems: list[str] = []
        seen: set[str] = set()
        for item in self.items:
            if item.id in seen:
                problems.append(f"id duplicado: {item.id}")
            seen.add(item.id)
            if item.source is Source.CONTROL:
                if item.control is None:
                    problems.append(f"{item.id}: controle sem tipo")
                if any(r.truth.strip() for r in item.regions):
                    problems.append(f"{item.id}: controle negativo com texto de verdade")
                continue
            if not item.regions:
                problems.append(f"{item.id}: item sem regiões")
            if item.source is Source.SYNTH and not item.synth_font:
                problems.append(f"{item.id}: item sintético sem fonte")
            if item.source in (Source.PDF_NATIVE, Source.PDF_SCAN) and (
                    not item.book or item.page_index < 0):
                problems.append(f"{item.id}: item de PDF sem livro ou página")
            for region in item.regions:
                if not normalise(region.truth):
                    problems.append(f"{item.id}: região {region.reading_order} vazia")
            unknown = [s for s in item.strata if s not in DEGRADATIONS]
            if unknown:
                problems.append(f"{item.id}: estratos desconhecidos {unknown}")
            orders = [r.reading_order for r in item.regions]
            if len(set(orders)) != len(orders):
                problems.append(f"{item.id}: ordem de leitura repetida")
        return problems

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "corpus_version": self.corpus_version,
            "built_at": self.built_at,
            "partition_shares": list(PARTITION_SHARES),
            "strata": self.strata,
            "notes": self.notes,
            "items": [i.as_dict() for i in self.items],
        }


def load_manifest(path: Path | str, *, include_blind: bool = False) -> GoldenManifest:
    """Read a manifest.  The blind partition is withheld unless asked for."""
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if int(data.get("version", 0)) != MANIFEST_VERSION:
        raise ValueError(
            f"manifesto na versão {data.get('version')}, esperada {MANIFEST_VERSION}")
    items = [GoldenItem.from_dict(row) for row in data.get("items", ())]
    if not include_blind:
        items = [i for i in items if i.partition is not Partition.BLIND]
    manifest = GoldenManifest(
        items=items,
        version=MANIFEST_VERSION,
        corpus_version=str(data.get("corpus_version", "0")),
        built_at=str(data.get("built_at", "")),
        notes=list(data.get("notes", ())),
        strata=dict(data.get("strata", {})),
    )
    problems = manifest.validate()
    if problems:
        raise ValueError("manifesto inválido: " + "; ".join(problems[:5]))
    return manifest


def save_manifest(manifest: GoldenManifest, path: Path | str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(manifest.as_dict(), handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def items_sorted(items: Sequence[GoldenItem]) -> list[GoldenItem]:
    """Deterministic order for any run: by id."""
    return sorted(items, key=lambda i: i.id)
