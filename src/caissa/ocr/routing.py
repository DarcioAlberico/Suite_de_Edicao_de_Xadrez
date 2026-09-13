"""Engine routing by evidence — Sol §SOL-4.

The cascade used to run engines in level order, always: text layer, then
Tesseract, then whatever heavier engine was installed, until one cleared
the bar.  Level order is a cost order, and cost is the right tie-break; it
is the wrong *first* criterion when the region itself says which engine is
likely to read it.  A Cyrillic block on a page whose language hint is
Russian is not a job for a Latin-tuned cascade to fail at first; a table is
a job for a layout engine; and a region that two engines disagree about
needs a third opinion more than it needs the cheapest one.

So the router orders the *eligible* engines by a small table of routes
(Sol §SOL-4, "Roteamento inicial") and lets the arbiter run them in that
order with the usual escalation.  It never removes an engine — the budget
and the thresholds still decide how far the cascade goes — and it never
reorders level 0: the PDF's own text layer is always first when a PDF page
is available, because reading is cheaper and better than recognising.

The table is data, in one place, so a measured change is a data change:

===================================  =====================================
condition                            preferred order (then level order)
===================================  =====================================
PDF page available                   ``pdf_text_layer`` first
Cyrillic language or script          ``surya``, ``paddleocr``, ``rapidocr``
table region                         ``paddle_structure``, ``paddleocr``
movetext region                      ``tesseract`` (movetext profile, §SOL-7)
plain Latin prose                    ``tesseract``
===================================  =====================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .engines.base import OcrEngine
from .lexicon import normalise_lang
from .types import RegionKind

__all__ = ["Route", "Router", "DEFAULT_ROUTES"]

CYRILLIC_LANGS = frozenset({"rus", "ukr", "bul", "srp", "mkd", "bel"})


@dataclass(frozen=True, slots=True)
class Route:
    """One row of the table: when it applies and which engines it prefers."""

    name: str
    preferred: tuple[str, ...]
    reason_pt: str


DEFAULT_ROUTES: dict[str, Route] = {
    "cyrillic": Route("cyrillic", ("surya", "paddleocr", "rapidocr", "tesseract"),
                      "cirílico ou script difícil: motores multilíngues antes do Tesseract"),
    "table": Route("table", ("paddle_structure", "paddleocr", "tesseract"),
                   "tabela ou leiaute complexo: motor de estrutura antes do Tesseract"),
    "movetext": Route("movetext", ("tesseract",),
                      "lances: Tesseract com perfil de notação"),
    "prose": Route("prose", ("tesseract",), "prosa latina simples: Tesseract"),
}


@dataclass(slots=True)
class Router:
    routes: dict[str, Route] = field(default_factory=lambda: dict(DEFAULT_ROUTES))

    def route_for(self, task: Any) -> Route:
        """The route a task falls under, from its language, script and kind."""
        langs = normalise_lang(getattr(task, "lang", "") or "")
        script = str(getattr(task, "script_hint", "") or "")
        kind = getattr(task, "region_kind", RegionKind.UNKNOWN)
        if script == "cyrillic" or (langs and langs[0] in CYRILLIC_LANGS):
            return self.routes["cyrillic"]
        if kind is RegionKind.TABLE:
            return self.routes["table"]
        if kind is RegionKind.MOVETEXT:
            return self.routes["movetext"]
        return self.routes["prose"]

    def order(self, engines: Sequence[OcrEngine], task: Any) -> list[OcrEngine]:
        """``engines`` reordered for ``task``.  Deterministic; nothing dropped."""
        route = self.route_for(task)
        rank = {name: n for n, name in enumerate(route.preferred)}

        def key(engine: OcrEngine) -> tuple[int, int, int, str]:
            caps = engine.capabilities()
            page_first = 0 if caps.requires_pdf_page else 1
            return (page_first, rank.get(engine.name, len(rank)), caps.level, engine.name)

        return sorted(engines, key=key)
