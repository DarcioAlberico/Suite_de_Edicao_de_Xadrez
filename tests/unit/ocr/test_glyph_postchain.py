"""The trunk's page chain inside the glyph reader (OCR_UI_ROADMAP_C2 §B7):
stacked pairs fused with the bars the aspect rule rejects, the glued cut
judged by the classifier, ``=`` told from ``:`` by aspect, and the margin
(``1 - p2/p1``) exposed on every glyph and on the word the fusion sees."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
import pytest

from caissa.ocr.engines.glyph import (
    GLUED_NEVER,
    GlyphBox,
    GlyphEngine,
    GlyphWord,
    margins_from_probabilities,
    words_from_glyphs,
)
from caissa.ocr.types import BBox, OcrWord


def _glyph(text: str, x: float, margin: float | None, conf: float = 0.9) -> GlyphBox:
    return GlyphBox(text=text, confidence=conf, box=BBox(x, 0.0, 10.0, 14.0), margin=margin)


def test_margins_are_the_trunks_formula_over_the_probability_matrix():
    probs = np.array([[0.8, 0.1, 0.1], [0.5, 0.5, 0.0], [1.0, 0.0, 0.0]], dtype=np.float32)
    assert margins_from_probabilities(probs) == pytest.approx([0.875, 0.0, 1.0])
    assert margins_from_probabilities(np.empty((0, 3), np.float32)) == []


def test_a_word_carries_the_smallest_margin_of_its_glyphs():
    words = words_from_glyphs([_glyph("♖", 0, 0.95), _glyph("e", 10, 0.40), _glyph("8", 20, 0.99)])
    assert len(words) == 1
    word = words[0]
    assert isinstance(word, GlyphWord)
    assert isinstance(word, OcrWord)
    assert word.margin == pytest.approx(0.40)
    assert getattr(word, "margin", None) == pytest.approx(0.40), "the fusion's accessor"
    # A hand-built glyph without a margin leaves the word without one: no number is invented.
    words = words_from_glyphs([_glyph("♖", 0, 0.95), _glyph("e", 10, None)])
    assert words[0].margin is None


# --------------------------------------------------------------------------- #
# The chain, with a fake trunk: order, parameters and the two switches
# --------------------------------------------------------------------------- #


@dataclass
class Caixa:
    x1: int
    y1: int
    x2: int
    y2: int
    angulo: int = 0

    @property
    def largura(self) -> int:
        return self.x2 - self.x1

    @property
    def altura(self) -> int:
        return self.y2 - self.y1

    def recortar(self, imagem):
        return imagem[self.y1 : self.y2, self.x1 : self.x2]


class FakeMeta:
    num_classes = 3
    idx_to_char: ClassVar[dict[int, str]] = {0: "=", 1: ":", 2: "a"}
    modelo_sha256 = "fake"


class FakeClassifier:
    """Answers ``:`` for every box with a flat second choice, so the aspect
    correction has something to overturn and the margin something to say."""

    meta = FakeMeta()

    def probabilidades(self, recortes):
        return np.array([[0.30, 0.60, 0.10]] * len(recortes), dtype=np.float32)

    def classificar(self, recortes):
        return [(":", 0.6)] * len(recortes)


class FakeTrunk(dict):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []
        self["binarize"] = lambda g: (g < 128).astype(np.uint8) * 255
        self["escala_de_texto"] = lambda b: 20
        # One wide box (an ``=``, 40×14) and one narrow letter.
        self["caixas_de_caractere"] = lambda b, escala: [Caixa(0, 0, 40, 14), Caixa(50, 0, 60, 14)]
        self["unir_pingos"] = self._rec("unir_pingos", lambda caixas, **kw: list(caixas))
        self["barras"] = self._rec("barras", lambda b, escala: [Caixa(70, 2, 90, 5)])
        self["unir_empilhados"] = self._rec(
            "unir_empilhados", lambda caixas, escala, extras=(): [*caixas, *extras]
        )
        self["ordem_em_faixa"] = lambda caixas: list(caixas)
        self["separar_colados"] = self._rec(
            "separar_colados", lambda binaria, caixas, **kw: list(caixas)
        )
        self["quebrar_em_linhas"] = lambda caixas: [list(caixas)]
        self["descartar_fragmentos"] = lambda linhas, escala: [list(ln) for ln in linhas]
        self["corrigir_empilhados"] = self._rec(
            "corrigir_empilhados",
            lambda lidos, probs, caixas, i2c: [
                ("=", float(probs[k, 0])) if caixas[k].largura >= caixas[k].altura else lido
                for k, lido in enumerate(lidos)
            ],
        )
        self["corrigir_numero"] = self._rec("corrigir_numero", lambda lidos, *a: list(lidos))

    def _rec(self, name, fn):
        def wrapped(*args, **kwargs):
            self.calls.append((name, kwargs))
            return fn(*args, **kwargs)

        return wrapped

    def names(self) -> list[str]:
        return [n for n, _ in self.calls]


def _engine(**flags) -> tuple[GlyphEngine, FakeTrunk]:
    engine = GlyphEngine(**flags)
    trunk = FakeTrunk()
    engine._trunk = trunk
    engine._classifier = FakeClassifier()
    engine._available = True
    return engine, trunk


def test_the_chain_runs_in_the_trunks_order_with_the_trunks_parameters():
    engine, trunk = _engine()
    lines = engine.read_glyphs(np.full((30, 100), 255, np.uint8))
    assert trunk.names() == [
        "unir_pingos",
        "barras",
        "unir_empilhados",
        "separar_colados",
        "corrigir_empilhados",
        "corrigir_numero",
    ]
    by_name = dict(trunk.calls)
    assert by_name["unir_pingos"]["binaria"] is not None, "the italic dot needs the binary image"
    assert [c.x1 for c in by_name["unir_empilhados"]["extras"]] == [70], "the bars are the extras"
    assert callable(by_name["separar_colados"]["arbitro"]), "never cut without the arbiter"
    assert by_name["separar_colados"]["modo"] == "auto"
    # The bar pair came back as a box, the wide boxes read ``=`` by aspect, the narrow one ``:``.
    assert len(lines) == 1
    assert [g.text for g in lines[0]] == ["=", ":", "="]
    assert lines[0][0].confidence == pytest.approx(0.30), "the confidence of the class chosen"
    assert all(g.margin == pytest.approx(0.5) for g in lines[0]), "1 - 0.30/0.60"


def test_stacked_off_skips_both_halves_of_the_stacked_rule():
    engine, trunk = _engine(stacked=False)
    lines = engine.read_glyphs(np.full((30, 100), 255, np.uint8))
    assert "unir_empilhados" not in trunk.names()
    assert "barras" not in trunk.names()
    assert "corrigir_empilhados" not in trunk.names()
    assert [g.text for g in lines[0]] == [":", ":"], "the bar never enters; the aspect never speaks"


def test_glued_never_skips_the_separator():
    engine, trunk = _engine(glued=GLUED_NEVER)
    engine.read_glyphs(np.full((30, 100), 255, np.uint8))
    assert "separar_colados" not in trunk.names()


def test_the_arbiter_is_the_classifiers_mean_confidence():
    engine, _ = _engine()
    judge = engine._arbiter(np.full((30, 100), 255, np.uint8))
    assert judge([Caixa(0, 0, 10, 10), Caixa(10, 0, 20, 10)]) == pytest.approx(0.6)
    assert judge([Caixa(0, 0, 0, 10)]) == 0.0, "an empty crop is no evidence"


# --------------------------------------------------------------------------- #
# The real trunk on a drawn ``=``: the recall-zero mechanism itself
# --------------------------------------------------------------------------- #


def _page_with_an_equals_sign() -> tuple[np.ndarray, BBox]:
    """Letter-sized blocks to set the text scale, then two bars: an ``=``.

    The page is large enough for an 18×30 block to count as a character
    when the scale is measured (``FRACAO_MAXIMA_DE_CARACTERE`` = 1 %).
    """
    page = np.full((200, 600), 255, np.uint8)
    for k in range(8):
        x = 10 + k * 30
        page[80:110, x : x + 18] = 0  # 18×30 "letters"
    bars = BBox.from_edges(300.0, 90.0, 324.0, 101.0)
    page[90:93, 300:324] = 0
    page[98:101, 300:324] = 0
    return page, bars


def test_the_real_trunk_fuses_the_two_bars_only_with_stacked_on():
    engine = GlyphEngine()
    if not engine.available():
        pytest.skip(engine.unavailable_reason() or "sem tronco")
    page, bars = _page_with_an_equals_sign()

    def over_the_bars(engine: GlyphEngine) -> list[GlyphBox]:
        return [
            g
            for line in engine.read_glyphs(page)
            for g in line
            if g.box.intersection(bars).area > 0
        ]

    fused = over_the_bars(engine)
    assert len(fused) == 1, "the two bars are one box"
    assert fused[0].box.h >= bars.h - 1, "the box spans both bars"
    assert fused[0].margin is not None
    assert 0.0 <= fused[0].margin <= 1.0
    engine.stacked = False
    assert over_the_bars(engine) == [], "without the bars, an ``=`` never reaches the classifier"
