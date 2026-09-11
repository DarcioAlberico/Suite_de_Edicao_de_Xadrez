"""Fixtures for the typography front.

Two things every test here needs.

**Real fonts, or an honest skip.** Nothing in this package can be tested against a
fabricated font: a glyph table is only meaningful next to the file it claims to
describe. So the fixtures resolve real families through `fonts.available_specs`, and a
test that needs one it cannot find *skips with the reason*, rather than passing against
a stub and telling us nothing.

**The fontTools date warnings.** Several of the chess fonts on this machine are from the
1990s and carry a `head.created` outside the range fontTools expects; it warns on every
open. The project turns warnings into errors, which is right, so the two known-benign
ones are filtered here -- narrowly, by message, not by blanket-ignoring warnings.
"""

from __future__ import annotations

import warnings

import pytest

from caissa.typeset import fonts


def pytest_configure(config):  # noqa: ANN001, ANN201
    for message in (
        r".*timestamp.*out of range.*",
        r".*timestamp seems very low.*",
    ):
        warnings.filterwarnings("ignore", message=message)
        config.addinivalue_line("filterwarnings", f"ignore:{message[2:-2]}")


@pytest.fixture(scope="session")
def verified_specs() -> list[fonts.ChessFontSpec]:
    """Every family that is installed *and* passes `verify_spec` on this machine."""
    found = [
        spec
        for spec in fonts.available_specs()
        if spec.confidence is fonts.Confidence.VERIFIED
    ]
    if not found:
        pytest.skip(
            "Nenhuma familia de xadrez VERIFIED instalada nesta maquina. "
            "Instale ao menos uma (por exemplo ChessMerida.ttf) ou aponte "
            "CAISSA_FONT_PATH para uma pasta com fontes."
        )
    return found


@pytest.fixture(scope="session")
def legacy_spec(verified_specs) -> fonts.ChessFontSpec:
    """One verified legacy (ASCII-mapped) family; Merida when it is present."""
    for spec in verified_specs:
        if spec.key == "merida":
            return spec
    for spec in verified_specs:
        if spec.model is fonts.FontModel.LEGACY:
            return spec
    pytest.skip("Nenhuma familia legada VERIFIED disponivel.")


@pytest.fixture(scope="session")
def legacy_font(legacy_spec) -> fonts.LoadedFont:
    return fonts.load_font(legacy_spec)
