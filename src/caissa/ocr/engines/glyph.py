"""The figurine reader — the trunk's glyph classifier as an OCR engine.

No line engine reads a figurine, because a figurine is not a letter: the
Windows ``eng.traineddata`` has no ♖ in its alphabet, so Tesseract returns
the nearest Latin shape (``♖e8!`` → ``Hea!``) and :mod:`caissa.ocr.notation.cipher`
has to infer the piece back from consistency and legality.  The sibling
ChessVisionOFF trunk has a *glyph* classifier that was trained on exactly
these shapes — 314 classes including ♔♕♖♗♘♙ and the ligatures a metal
font glues (``♕x``, ``♗a``) — and reads ``36... ♖e8!`` as written.

This adapter runs that classifier as a **second opinion, not a cascade
level**: it is not registered in the engine table, because it is a glyph
reader, not a page reader (its prose is a little worse than Tesseract's —
``lf`` for ``If``, ``4o`` for ``40``).  :class:`~caissa.ingest.pdf.ocr_service.OcrService`
asks it for a candidate on regions that look like notation, and the token
fusion of Sol §SOL-6 does the rest with its own rules: an anchor token
that is already a word or a move is never touched, an anchor token that is
neither (``Hea!``) is replaced by a supported reading that overlaps it
(``♖e8!``).  The prose stays Tesseract's; the figurines become figurines.

The trunk is absorbed, never rewritten (``docs/ASSETS.md``): the
segmentation and the classifier are the trunk's own functions, reached
through :mod:`caissa.vision.classify.cvoff`.  What is added here is the
one thing the fusion needs and the trunk's ``read()`` folds away — a box
per glyph, grouped into words by the trunk's own space rule.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
from numpy.typing import NDArray

from caissa.ocr.engines.base import (
    EngineCapabilities,
    EngineLevel,
    OcrEngineBase,
    normalise_gray,
)
from caissa.ocr.types import BBox, OcrChar, OcrLine, OcrResult, OcrWord, RegionKind

__all__ = ["GlyphBox", "GlyphEngine", "default_glyph_engine", "words_from_glyphs"]

ENGINE_NAME = "glyph"

#: The trunk's ``VAO_DE_ESPACO``: a gap wider than this share of the median
#: glyph width is a space.  Mirrored rather than imported so the word rule
#: is testable without the trunk.
SPACE_GAP_SHARE = 0.42
#: Marks that attach to the preceding token regardless of the gap.
ATTACHED_MARKS = ".!?+#,;:"

MISSING_TRUNK_PT = (
    "O leitor de figurinas precisa do tronco ChessVisionOFF_Puro (pasta ao lado do projeto "
    "ou $CAISSA_CVOFF_ROOT) com models/char_classifier.pt e models/char_meta.json."
)


@dataclass(frozen=True, slots=True)
class GlyphBox:
    """One classified glyph in the pixel space of the image read."""

    text: str
    confidence: float
    box: BBox


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[len(ordered) // 2])


def words_from_glyphs(
    glyphs: Sequence[GlyphBox], *, gap_share: float = SPACE_GAP_SHARE
) -> list[OcrWord]:
    """Group glyphs of one line into words, the trunk's way.

    A gap wider than ``gap_share`` × the median glyph width is a space.  A
    ligature class (``♕x``) is one box with two characters; its characters
    share the box, split proportionally, so the fusion's per-character
    fallback still points somewhere sensible.  Word confidence is the
    minimum of its glyphs — a word with one guessed glyph is a guessed word.
    """
    if not glyphs:
        return []
    ordered = sorted(glyphs, key=lambda g: g.box.x0)
    limit = gap_share * (_median([g.box.w for g in ordered]) or 1.0)
    groups: list[list[GlyphBox]] = [[ordered[0]]]
    for previous, current in pairwise(ordered):
        # A lone mark (``!``, ``+``, the dots of ``36...``) belongs to the
        # token before it however wide the font sets the gap: chess marks
        # are never words of their own.
        lone_mark = bool(current.text.strip()) and all(c in ATTACHED_MARKS for c in current.text)
        if current.box.x0 - previous.box.x1 > limit and not lone_mark:
            groups.append([current])
        else:
            groups[-1].append(current)
    words: list[OcrWord] = []
    for n, group in enumerate(groups):
        chars: list[OcrChar] = []
        for glyph in group:
            text = glyph.text
            if not text:
                continue
            share = glyph.box.w / len(text)
            for k, ch in enumerate(text):
                chars.append(
                    OcrChar(
                        text=ch,
                        box=BBox(glyph.box.x + share * k, glyph.box.y, share, glyph.box.h),
                        confidence=glyph.confidence,
                        inherited_confidence=len(text) > 1,
                    )
                )
        text = "".join(g.text for g in group)
        if not text.strip():
            continue
        words.append(
            OcrWord(
                text=text,
                box=BBox.union_of([g.box for g in group]),
                confidence=min(g.confidence for g in group),
                chars=tuple(chars),
                word_index=n,
            )
        )
    return words


class GlyphEngine(OcrEngineBase):
    """The trunk's glyph classifier behind the :class:`OcrEngine` protocol."""

    name = ENGINE_NAME

    def __init__(self, meta_path: str | None = None, model_path: str | None = None) -> None:
        super().__init__()
        self.meta_path = meta_path
        self.model_path = model_path
        self._classifier: Any = None
        self._trunk: Any = None
        self._version: str | None = None

    # -- availability ------------------------------------------------------ #

    def _probe(self) -> tuple[bool, str | None]:
        try:
            from caissa.vision.classify.cvoff import ensure_cvoff_on_path

            ensure_cvoff_on_path()
            from chess_diagram_ocr.text import binarizacao, boxes, duas_linhas, linhas
            from chess_diagram_ocr.text.modelo import CAMINHO_PADRAO_META, carregar_classificador
        except FileNotFoundError as exc:
            return False, f"{MISSING_TRUNK_PT} ({exc})"
        except ImportError as exc:
            return False, f"{MISSING_TRUNK_PT} Módulo ausente: {exc}"
        try:
            from pathlib import Path

            meta = Path(self.meta_path) if self.meta_path else CAMINHO_PADRAO_META
            weights = Path(self.model_path) if self.model_path else None
            self._classifier = carregar_classificador(meta, weights)
        except Exception as exc:  # noqa: BLE001 - the trunk's own diagnosis is the message
            return False, f"Classificador de glifos não carregou: {exc}"
        self._trunk = {
            "binarize": binarizacao.binarize,
            "escala_de_texto": boxes.escala_de_texto,
            "caixas_de_caractere": boxes.caixas_de_caractere,
            "unir_pingos": boxes.unir_pingos,
            "ordem_em_faixa": linhas.ordem_em_faixa,
            "quebrar_em_linhas": linhas.quebrar_em_linhas,
            "descartar_fragmentos": duas_linhas.descartar_fragmentos,
        }
        meta_obj = self._classifier.meta
        self._version = (
            f"char_classifier {meta_obj.num_classes} classes "
            f"{str(getattr(meta_obj, 'modelo_sha256', ''))[:12]}"
        )
        return True, None

    @property
    def version(self) -> str | None:
        self.available()
        return self._version

    def _discover_languages(self) -> set[str]:
        # Figurines are the same in every language; the classifier's Latin
        # classes serve any Latin-script book.  Cyrillic prose is not its job.
        return {"eng", "por", "deu", "spa", "fra", "ita", "nld", "ron"}

    # ``supports_language`` is the base class's: every part of ``rus+eng`` must
    # be a language the classifier serves, and Cyrillic is not — on a Russian
    # page its Latin classes read Ф as a figurine and invent moves.

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            level=EngineLevel.TESSERACT,
            cost_per_megapixel_s=0.8,
            supports_char_boxes=True,
            supports_confidence=True,
            handles_layout=False,
            requires_pdf_page=False,
            gpu_capable=True,
        )

    # -- recognition ------------------------------------------------------- #

    def read_glyphs(
        self, image: NDArray[np.uint8], strips: Sequence[BBox] | None = None
    ) -> list[list[GlyphBox]]:
        """Lines of classified glyphs, in the pixel space of ``image``.

        With ``strips`` (line boxes the caller already knows), each strip is
        segmented on its own so two columns are never merged into one line,
        while the text scale — which a short strip cannot measure — comes
        from the whole image.
        """
        gray = normalise_gray(image)
        trunk = self._trunk
        binary = trunk["binarize"](gray)
        scale = trunk["escala_de_texto"](binary)
        if not scale:
            return []
        h, w = gray.shape[:2]
        windows: list[tuple[int, int, int, int]] = []
        if strips:
            pad = max(2, int(scale) // 4)
            for strip in strips:
                x0 = max(0, int(strip.x0) - pad)
                y0 = max(0, int(strip.y0) - pad)
                x1 = min(w, round(strip.x1) + pad)
                y1 = min(h, round(strip.y1) + pad)
                if x1 - x0 > 1 and y1 - y0 > 1:
                    windows.append((x0, y0, x1, y1))
        else:
            windows.append((0, 0, w, h))
        out: list[list[GlyphBox]] = []
        for x0, y0, x1, y1 in windows:
            sub_binary = binary[y0:y1, x0:x1]
            sub_gray = gray[y0:y1, x0:x1]
            boxes = trunk["unir_pingos"](
                trunk["caixas_de_caractere"](sub_binary, escala=scale), escala=scale
            )
            groups = trunk["descartar_fragmentos"](
                trunk["quebrar_em_linhas"](trunk["ordem_em_faixa"](boxes)), escala=scale
            )
            for group in groups:
                if not group or any(getattr(c, "angulo", 0) for c in group):
                    continue
                readings = self._classifier.classificar([c.recortar(sub_gray) for c in group])
                if len(readings) != len(group):
                    continue
                out.append(
                    [
                        GlyphBox(
                            text=str(text),
                            confidence=float(conf),
                            box=BBox.from_edges(
                                float(c.x1 + x0),
                                float(c.y1 + y0),
                                float(c.x2 + x0),
                                float(c.y2 + y0),
                            ),
                        )
                        for c, (text, conf) in zip(group, readings, strict=True)
                    ]
                )
        return out

    def _result(
        self,
        glyph_lines: Sequence[Sequence[GlyphBox]],
        *,
        lang: str,
        psm_hint: RegionKind,
        started: float,
    ) -> OcrResult:
        lines: list[OcrLine] = []
        for n, glyphs in enumerate(glyph_lines):
            words = words_from_glyphs(glyphs)
            if not words:
                continue
            lines.append(
                OcrLine(
                    words=tuple(words),
                    box=BBox.union_of([w.box for w in words]),
                    line_index=n,
                    kind=psm_hint,
                )
            )
        return OcrResult(
            engine=self.name,
            lang=lang,
            lines=tuple(lines),
            region_kind=psm_hint,
            duration_s=time.perf_counter() - started,
            meta={"model": self._version or "", "role": "figurine second opinion"},
        )

    def _recognize(self, image: NDArray[np.uint8], *, lang: str, psm_hint: RegionKind) -> OcrResult:
        started = time.perf_counter()
        return self._result(self.read_glyphs(image), lang=lang, psm_hint=psm_hint, started=started)

    def recognize_lines(
        self,
        image: NDArray[np.uint8],
        strips: Sequence[BBox],
        *,
        lang: str,
        psm_hint: RegionKind = RegionKind.MOVETEXT,
    ) -> OcrResult:
        """Read the given line strips of ``image`` (boxes in its pixel space)."""
        started = time.perf_counter()
        if not self.available():
            return self.recognize(image, lang=lang, psm_hint=psm_hint)
        return self._result(
            self.read_glyphs(image, strips), lang=lang, psm_hint=psm_hint, started=started
        )


_DEFAULT: GlyphEngine | None = None


def default_glyph_engine() -> GlyphEngine:
    """One engine per process — the classifier is loaded once."""
    global _DEFAULT  # noqa: PLW0603 - one lazily built engine per process
    if _DEFAULT is None:
        _DEFAULT = GlyphEngine()
    return _DEFAULT
