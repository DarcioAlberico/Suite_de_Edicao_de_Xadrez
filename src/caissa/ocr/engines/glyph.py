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

The segmentation is the trunk's *page* chain (``text/leitor.py``
``segmentar`` → ``linhas_do_glifo``), not the bare contour pass the first
version ran (OCR_UI_ANALISE_C2 §5.5): ``unir_pingos`` with the binary
image (the italic ``i``), ``empilhados.unir`` with the bars the aspect
rule rejects (``:``, ``;`` and ``=`` are two contours each — without it
their recall is zero and ``g1=♕`` reads ``g1 ♕``), ``colados.separar``
with the classifier as arbiter (never without one: 2.3 F1 points in the
trunk's origin project), and after the classifier ``empilhados.corrigir``
(the 32×32 resize erases the aspect that tells ``=`` from ``:``) and
``numero.corrigir`` (``4o`` → ``40``, ``o-o-o`` → ``0-0-0``).  The lexicon
and the move-number joiner stay out: the fusion has its own lexicon, and
the words are grouped here, after the boxes, by :func:`words_from_glyphs`.
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

__all__ = [
    "GlyphBox",
    "GlyphEngine",
    "GlyphWord",
    "default_glyph_engine",
    "margins_from_probabilities",
    "words_from_glyphs",
]

ENGINE_NAME = "glyph"

#: ``colados.separar`` modes, mirrored so the engine's flags are readable
#: without the trunk.  ``"auto"`` asks the arbiter; ``"nunca"`` never cuts.
GLUED_AUTO = "auto"
GLUED_NEVER = "nunca"

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
    """One classified glyph in the pixel space of the image read.

    ``margin`` is the trunk's ``ClassificadorDeGlifo.margem``: ``1 - p2/p1``
    over the classifier's probabilities — was the winner clearly ahead of
    the runner-up?  A confidence of 0.80 with a margin of 0.95 is a sure
    glyph with a flat tail; 0.80 with a margin of 0.10 is a coin toss with
    one other shape.  ``None`` when the glyph did not come from the
    classifier's probability matrix (a hand-built box in a test).
    """

    text: str
    confidence: float
    box: BBox
    margin: float | None = None


@dataclass(frozen=True, slots=True)
class GlyphWord(OcrWord):
    """An :class:`OcrWord` that carries the glyph reader's ``margin``.

    The fusion reads it as ``getattr(word, "margin", None)`` — a second
    criterion, next to ``confidence``, for the look-alike → figurine swap.
    A word's margin is the smallest of its glyphs, like its confidence: a
    word with one doubtful glyph is a doubtful word.
    """

    margin: float | None = None


def margins_from_probabilities(probs: NDArray[np.floating]) -> list[float]:
    """The trunk's ``margem`` over an already computed probability matrix.

    ``1 - p2/p1`` per row, clipped to ``[0, 1]`` (``text/modelo.py``).
    Computed here rather than through ``classificador.margem`` because that
    method runs the network again; the probabilities are already in hand.
    """
    if probs.size == 0:
        return []
    if probs.shape[1] == 1:
        probs = np.hstack([np.zeros((probs.shape[0], 1)), probs])
    two = np.sort(probs, axis=1)[:, -2:]
    p1, p2 = two[:, 1], two[:, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        margins = np.where(p1 > 0.0, 1.0 - p2 / p1, 0.0)
    return [float(min(1.0, max(0.0, m))) for m in margins]


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
        margins = [g.margin for g in group if g.margin is not None]
        words.append(
            GlyphWord(
                text=text,
                box=BBox.union_of([g.box for g in group]),
                confidence=min(g.confidence for g in group),
                chars=tuple(chars),
                word_index=n,
                margin=min(margins) if len(margins) == len(group) else None,
            )
        )
    return words


class GlyphEngine(OcrEngineBase):
    """The trunk's glyph classifier behind the :class:`OcrEngine` protocol."""

    name = ENGINE_NAME

    def __init__(
        self,
        meta_path: str | None = None,
        model_path: str | None = None,
        *,
        stacked: bool = True,
        glued: str = GLUED_AUTO,
        numbers: bool = True,
    ) -> None:
        super().__init__()
        self.meta_path = meta_path
        self.model_path = model_path
        #: ``empilhados``: fuse the two contours of ``:`` ``;`` ``=`` (and
        #: tell ``=`` from ``:`` by aspect after the classifier).  Off only
        #: for the sabotage of OCR_UI_ROADMAP_C2 §B7 — their recall is 0.
        self.stacked = stacked
        #: ``colados.separar`` mode: ``"auto"`` cuts a two-glyph contour where
        #: the classifier confirms the cut, ``"nunca"`` leaves every box.
        self.glued = glued
        #: ``numero.corrigir``: the oval inside a number is a zero, the
        #: ``O.O`` is a castling.
        self.numbers = numbers
        self._classifier: Any = None
        self._trunk: Any = None
        self._version: str | None = None

    # -- availability ------------------------------------------------------ #

    def _probe(self) -> tuple[bool, str | None]:
        try:
            from caissa.vision.classify.cvoff import ensure_cvoff_on_path

            ensure_cvoff_on_path()
            from chess_diagram_ocr.text import (
                binarizacao,
                boxes,
                colados,
                duas_linhas,
                empilhados,
                linhas,
                numero,
            )
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
            # The page chain of ``text/leitor.py`` (``segmentar`` / ``linhas_do_glifo``).
            "barras": empilhados.barras,
            "unir_empilhados": empilhados.unir,
            "corrigir_empilhados": empilhados.corrigir,
            "separar_colados": colados.separar,
            "corrigir_numero": numero.corrigir,
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
            sub_binary = np.ascontiguousarray(binary[y0:y1, x0:x1])
            sub_gray = np.ascontiguousarray(gray[y0:y1, x0:x1])
            boxes = self._segment(sub_binary, sub_gray, scale)
            groups = trunk["descartar_fragmentos"](
                trunk["quebrar_em_linhas"](trunk["ordem_em_faixa"](boxes)), escala=scale
            )
            for group in groups:
                if not group or any(getattr(c, "angulo", 0) for c in group):
                    continue
                readings, margins = self._classify(group, sub_gray)
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
                            margin=margin,
                        )
                        for c, (text, conf), margin in zip(group, readings, margins, strict=True)
                    ]
                )
        return out

    def _segment(self, binary: NDArray[np.uint8], gray: NDArray[np.uint8], scale: int) -> list[Any]:
        """The character boxes of one window, the trunk's ``segmentar`` way.

        Same order and parameters as ``text/leitor.py``: the dots go back to
        their stems with the binary image (the italic ``i``), the stacked
        pairs are fused with the bars the aspect rule rejected (``=``), the
        order is restored, and a suspiciously wide box is cut only where
        the classifier itself confirms the two halves read better.
        """
        trunk = self._trunk
        boxes = trunk["unir_pingos"](
            trunk["caixas_de_caractere"](binary, escala=scale), escala=scale, binaria=binary
        )
        if self.stacked:
            boxes = trunk["unir_empilhados"](
                boxes, escala=scale, extras=trunk["barras"](binary, escala=scale)
            )
            boxes = trunk["ordem_em_faixa"](boxes)
        if self.glued != GLUED_NEVER and boxes:
            boxes = trunk["separar_colados"](
                binary, boxes, escala=scale, arbitro=self._arbiter(gray), modo=self.glued
            )
        return list(boxes)

    def _arbiter(self, gray: NDArray[np.uint8]) -> Any:
        """Boxes → their mean confidence: the trunk's ``_arbitro_de_confianca``.

        Written the same so the cut is judged by the rule it was measured with.
        """
        classifier = self._classifier

        def judge(boxes: Sequence[Any]) -> float:
            crops = [c.recortar(gray) for c in boxes]
            crops = [r for r in crops if r.size]
            if not crops:
                return 0.0
            read = classifier.classificar(crops)
            return float(sum(c for _, c in read) / len(read)) if read else 0.0

        return judge

    def _classify(
        self, group: Sequence[Any], gray: NDArray[np.uint8]
    ) -> tuple[list[tuple[str, float]], list[float | None]]:
        """``(readings, margins)`` for one line of boxes.

        The argmax, then the trunk's geometric corrections over the same
        probability matrix.
        """
        trunk = self._trunk
        classifier = self._classifier
        crops = [c.recortar(gray) for c in group]
        probs = classifier.probabilidades(crops)
        if probs.size == 0:
            return [], []
        i2c = classifier.meta.idx_to_char
        readings = [
            (i2c[int(probs[k].argmax())], float(probs[k].max())) for k in range(probs.shape[0])
        ]
        if self.stacked:
            # The resize erases the aspect along with the size: fused, ``=`` reads ``:``.
            readings = trunk["corrigir_empilhados"](readings, probs, group, i2c)
        if self.numbers:
            readings = trunk["corrigir_numero"](readings, probs, group, i2c)
        margins: list[float | None] = list(margins_from_probabilities(probs))
        return list(readings), margins

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
