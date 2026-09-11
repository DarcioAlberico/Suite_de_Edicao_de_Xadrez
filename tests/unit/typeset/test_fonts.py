"""Font discovery, glyph-table verification and subsetting.

The rule this file enforces is the one in `fonts.py`'s docstring: a mapping marked
VERIFIED must have been checked against a real file, and this suite re-runs that check
rather than trusting the recorded verdict. A registry that has drifted from the fonts on
the machine fails here.
"""

from __future__ import annotations

import io

import pytest

from caissa.typeset import fonts
from caissa.typeset.fonts import (
    CHESS_FONT_SPECS,
    PIECES,
    UNICODE_PIECES,
    Confidence,
    FontModel,
    FontNotFoundError,
    find_font_file,
    get_spec,
    load_font,
    subset_font,
    verify_spec,
)


# --------------------------------------------------------------------------- #
# The registry is data, and it must be consistent data
# --------------------------------------------------------------------------- #
def test_every_spec_declares_a_complete_table():
    for key, spec in CHESS_FONT_SPECS.items():
        if spec.model is FontModel.UNICODE:
            continue
        assert set(spec.light) == set(PIECES), f"{key}: tabela clara incompleta"
        assert set(spec.dark) == set(PIECES), f"{key}: tabela escura incompleta"


def test_no_two_pieces_share_a_character_in_one_table():
    """Two pieces on one character is the commonest way a hand-written table is wrong,
    and it renders as a board with two bishops and no knights."""
    for key, spec in CHESS_FONT_SPECS.items():
        if spec.model is FontModel.UNICODE:
            continue
        for name, table in (("clara", spec.light), ("escura", spec.dark)):
            chars = list(table.values())
            assert len(set(chars)) == len(chars), (
                f"{key}: caractere repetido na tabela {name}: {chars}"
            )


def test_unicode_table_covers_all_twelve_codepoints():
    assert set(UNICODE_PIECES) == set(PIECES)
    assert len(set(UNICODE_PIECES.values())) == 12
    for codepoint in UNICODE_PIECES.values():
        assert 0x2654 <= ord(codepoint) <= 0x265F


def test_get_spec_names_the_alternatives_when_it_fails():
    with pytest.raises(KeyError) as excinfo:
        get_spec("no-such-family")
    assert "merida" in str(excinfo.value), "o erro deve listar o que existe"


# --------------------------------------------------------------------------- #
# Verification is re-run, not trusted
# --------------------------------------------------------------------------- #
def test_recorded_confidence_matches_a_live_check(verified_specs):
    """The registry's `confidence` is evidence, so it has to survive re-measurement.

    This is the test that would catch a fabricated glyph table: a family recorded as
    VERIFIED whose file does not actually satisfy the structural invariants fails here.
    """
    mismatches: list[str] = []
    for spec in CHESS_FONT_SPECS.values():
        result = verify_spec(spec)
        if find_font_file(spec) is None:
            # Nothing to check against; the registry must not claim VERIFIED.
            if spec.confidence is Confidence.VERIFIED:
                mismatches.append(f"{spec.key}: VERIFIED sem arquivo de fonte")
            continue
        if result.confidence is not spec.confidence:
            mismatches.append(
                f"{spec.key}: registrado {spec.confidence.value}, "
                f"medido {result.confidence.value} ({'; '.join(result.problems)[:80]})"
            )
    assert not mismatches, "\n".join(mismatches)


def test_recorded_sha_matches_the_file_it_names():
    """A hash that names a different file re-opens the question the hash was recorded to
    close."""
    for spec in CHESS_FONT_SPECS.values():
        if not spec.verified_sha256:
            continue
        path = find_font_file(spec)
        if path is None:
            continue
        result = verify_spec(spec)
        assert result.sha256.startswith(spec.verified_sha256), (
            f"{spec.key}: sha registrado {spec.verified_sha256}, "
            f"arquivo atual {result.sha256[:16]} ({path})"
        )


def test_verified_families_draw_twelve_distinct_pieces(verified_specs):
    for spec in verified_specs:
        font = load_font(spec)
        shapes = {}
        for piece in PIECES:
            outline = font.piece_outline(piece)
            assert not outline.is_empty(), f"{spec.key}: {piece} sem contorno"
            shapes.setdefault(outline.to_svg_path(scale=1.0), []).append(piece)
        # White and black share a silhouette by design, so six distinct shapes is right.
        assert len(shapes) >= 6, f"{spec.key}: apenas {len(shapes)} formas distintas"


def test_verify_spec_rejects_a_deliberately_wrong_table(legacy_spec):
    """Sanity check on the checker: swap two pieces and it must notice."""
    from dataclasses import replace

    good = dict(legacy_spec.light)
    broken = dict(good)
    broken["N"], broken["R"] = good["R"], good["N"]
    spec = replace(legacy_spec, light=broken, key="broken-on-purpose")
    result = verify_spec(spec)
    assert result.confidence is not Confidence.VERIFIED
    assert result.problems


def test_verify_spec_on_a_missing_family_is_a_clean_negative():
    from dataclasses import replace

    spec = replace(
        CHESS_FONT_SPECS["merida"],
        key="ghost",
        file_names=("DefinitelyNotInstalled-XYZ.ttf",),
    )
    result = verify_spec(spec)
    assert result.confidence is Confidence.UNVERIFIED
    assert result.path is None
    assert result.problems


def test_load_font_raises_a_named_error_when_absent():
    from dataclasses import replace

    spec = replace(
        CHESS_FONT_SPECS["merida"], key="ghost", file_names=("Nope-XYZ.ttf",)
    )
    with pytest.raises(FontNotFoundError):
        load_font(spec)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def test_font_metrics_are_sane(legacy_font):
    assert legacy_font.units_per_em > 0
    assert legacy_font.ascender() > legacy_font.descender()
    assert 0 < legacy_font.cap_height() <= legacy_font.units_per_em * 1.2
    assert 0 < legacy_font.x_height() <= legacy_font.cap_height() * 1.2


def test_character_resolver_handles_the_symbol_cmap(legacy_font):
    """Legacy chess fonts are encoded three ways in the wild. A resolver that knows only
    the Unicode one silently draws nothing -- the board comes out blank."""
    for piece in PIECES:
        char = legacy_font.spec.artwork_char(piece)
        assert legacy_font.has_char(char), f"{char!r} nao resolvido em {legacy_font.spec.key}"


# --------------------------------------------------------------------------- #
# Subsetting
# --------------------------------------------------------------------------- #
def _glyph_count(data: bytes) -> tuple[int, set[str]]:
    from fontTools.ttLib import TTFont

    font = TTFont(io.BytesIO(data), fontNumber=0)
    names = set(font.getGlyphOrder())
    return len(names), names


def test_subset_keeps_every_requested_glyph_and_drops_the_rest(legacy_spec):
    """Both halves matter. Keeping too little breaks the book; keeping everything
    defeats the purpose of subsetting, which is what makes an EPUB shippable."""
    wanted = [legacy_spec.artwork_char(p) for p in PIECES]
    data = subset_font(legacy_spec, wanted, flavor=None)

    from fontTools.ttLib import TTFont

    subset = TTFont(io.BytesIO(data), fontNumber=0)
    cmap = subset.getBestCmap()
    for char in wanted:
        assert ord(char) in cmap, f"o subconjunto perdeu {char!r}"
        glyph = subset.getGlyphSet()[cmap[ord(char)]]
        assert glyph is not None

    full = TTFont(str(find_font_file(legacy_spec)), fontNumber=0)
    kept = len(subset.getGlyphOrder())
    original = len(full.getGlyphOrder())
    assert kept < original, (
        f"o subconjunto nao descartou nada: {kept} de {original} glifos"
    )
    # 12 pieces plus .notdef and any composites they need; a long way short of the
    # couple of hundred a full chess font carries.
    assert kept <= len(wanted) + 12, f"subconjunto grande demais: {kept} glifos"


def test_subset_synthesises_a_unicode_cmap(legacy_spec):
    """The point of §2.10. A legacy font may carry only a (3, 0) symbol cmap; embed that
    in an EPUB and the reader looks up U+0070, the font answers only to U+F070, and the
    book has no pieces. The subset must answer to plain ASCII."""
    from fontTools.ttLib import TTFont

    wanted = [legacy_spec.artwork_char(p) for p in PIECES]
    data = subset_font(legacy_spec, wanted, synthesize_unicode_cmap=True, flavor=None)
    subset = TTFont(io.BytesIO(data), fontNumber=0)

    unicode_tables = [
        t for t in subset["cmap"].tables if (t.platformID, t.platEncID) == (3, 1)
    ]
    assert unicode_tables, "nenhuma tabela cmap (3, 1) na fonte subconjuntada"
    mapped = unicode_tables[0].cmap
    for char in wanted:
        assert ord(char) in mapped, f"{char!r} ausente da cmap Unicode sintetizada"


def test_subset_is_deterministic(legacy_spec):
    """Two calls in the same second. Kept as it was, because the property is real --
    but it is *not* the test that catches the bug; see the next one for why."""
    wanted = [legacy_spec.artwork_char(p) for p in PIECES]
    first = subset_font(legacy_spec, wanted, flavor=None)
    assert subset_font(legacy_spec, wanted, flavor=None) == first


def test_subset_is_deterministic_across_a_second_boundary(legacy_spec, monkeypatch):
    """The cycle-10 critique found `test_subset_is_deterministic` failing 1 run in 12,
    and the whole suite red 1 run in 3. Both calls above normally land inside the same
    wall-clock second, and `head.modified` only moves when they do not -- so the old
    test passed by luck and failed by luck, which is worse than not existing.

    This one removes the luck instead of adding a `sleep`: it drives
    `fontTools.misc.timeTools.timestampNow`, the single function `head.compile` consults,
    forward by an hour between the two calls. Before the fix the two blobs differ in
    three bytes (offsets 67, 183, 207 on ChessMerida: the stamp and the two bytes of
    `checkSumAdjustment` that cover it); after it they are equal, deterministically,
    every run.

    The monkeypatch is also its own liveness proof: with the pin removed the assert
    below fails on *every* run rather than one in twelve.
    """
    from fontTools.ttLib.tables import _h_e_a_d

    wanted = [legacy_spec.artwork_char(p) for p in PIECES]
    clock = [0x7C259DC0]

    def fake_now() -> int:
        clock[0] += 3600
        return clock[0]

    monkeypatch.setattr(_h_e_a_d, "timestampNow", fake_now)

    first = subset_font(legacy_spec, wanted, flavor=None)
    second = subset_font(legacy_spec, wanted, flavor=None)
    if first != second:
        offsets = [i for i, (a, b) in enumerate(zip(first, second)) if a != b]
        raise AssertionError(
            f"subconjunto muda com o relogio: {len(offsets)} bytes diferem "
            f"nos offsets {offsets[:8]}"
        )


def test_subset_pins_the_modification_stamp_and_leaves_created_alone(legacy_spec):
    """`head.modified` is pinned to a fixed epoch so the bytes cannot drift; `created`
    is deliberately *not* pinned, and this asserts both halves so a future change to
    `pin_font_timestamp` cannot quietly start rewriting provenance.

    The pinned instant is also chosen so re-reading the subset is silent: fontTools
    warns (and this project turns warnings into errors) for any stamp strictly below
    `0x7C259DC0`.
    """
    from fontTools.ttLib import TTFont

    wanted = [legacy_spec.artwork_char(p) for p in PIECES]
    data = subset_font(legacy_spec, wanted, flavor=None)
    head = TTFont(io.BytesIO(data), fontNumber=0)["head"]

    assert head.modified == fonts.SUBSET_EPOCH, (
        f"head.modified = {head.modified}, esperado {fonts.SUBSET_EPOCH}"
    )
    assert head.modified >= 0x7C259DC0, "carimbo abaixo do limiar que faz fontTools avisar"

    source_created = TTFont(str(find_font_file(legacy_spec)), fontNumber=0)["head"].created
    assert head.created == source_created, (
        "o subconjunto reescreveu head.created; so head.modified deve ser fixado"
    )


def test_pin_font_timestamp_is_a_no_op_on_a_font_without_head():
    """The helper is public and `caissa/export/pdfwrite.py` is expected to call it on
    fonts this module never opened, so it must not explode on an odd one."""

    class _Bare:
        recalcTimestamp = True

        def get(self, key, default=None):  # noqa: ANN001, ANN201
            return default

    bare = _Bare()
    fonts.pin_font_timestamp(bare)
    assert bare.recalcTimestamp is True  # nothing to pin, nothing changed


def test_subset_refuses_an_empty_request(legacy_spec):
    with pytest.raises(ValueError):
        subset_font(legacy_spec, [])


def test_subset_refuses_characters_the_font_does_not_have(legacy_spec):
    with pytest.raises(ValueError):
        subset_font(legacy_spec, ["中", "文"])


@pytest.mark.parametrize("flavor", [None, "woff2"])
def test_subset_flavours_both_produce_a_readable_font(legacy_spec, flavor):
    from fontTools.ttLib import TTFont

    if flavor == "woff2" and not fonts.woff2_available():
        pytest.skip(
            "WOFF2 precisa do compressor Brotli, que nao esta instalado neste "
            "ambiente. Instale com: pip install 'fonttools[woff]'"
        )
    wanted = [legacy_spec.artwork_char(p) for p in PIECES]
    data = subset_font(legacy_spec, wanted, flavor=flavor)
    font = TTFont(io.BytesIO(data), fontNumber=0)
    assert font.getGlyphOrder()
    if flavor == "woff2":
        assert font.flavor == "woff2"


def test_woff2_without_brotli_says_what_to_install(legacy_spec):
    """The charter fails an error message that does not say what to do next. Without
    Brotli, fontTools raises `ImportError: No module named brotli` from three frames
    down; this turns it into an instruction."""
    if fonts.woff2_available():
        pytest.skip("Brotli esta instalado; o caminho de erro nao e alcancavel aqui.")
    wanted = [legacy_spec.artwork_char(p) for p in PIECES]
    with pytest.raises(fonts.FontUnreadableError) as excinfo:
        subset_font(legacy_spec, wanted, flavor="woff2")
    message = str(excinfo.value)
    assert "fonttools[woff]" in message
    assert "flavor=None" in message


def test_subset_is_smaller_than_the_original(legacy_spec):
    wanted = [legacy_spec.artwork_char(p) for p in PIECES]
    data = subset_font(legacy_spec, wanted, flavor=None)
    original = find_font_file(legacy_spec).stat().st_size
    assert len(data) < original, (
        f"subconjunto ({len(data)} B) nao e menor que o original ({original} B)"
    )


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def test_search_paths_honour_the_environment_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CAISSA_FONT_PATH", str(tmp_path))
    assert tmp_path in [p.resolve() for p in fonts.search_paths()]


def test_available_specs_is_a_subset_of_the_registry():
    keys = {s.key for s in fonts.available_specs()}
    assert keys <= set(CHESS_FONT_SPECS)


def test_verified_specs_all_have_files_and_pass(verified_specs):
    for spec in fonts.verified_specs():
        assert find_font_file(spec) is not None
        assert spec.confidence is Confidence.VERIFIED
