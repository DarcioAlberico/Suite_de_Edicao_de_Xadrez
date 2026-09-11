"""Where the integration tests are allowed to write.

A test that writes into a published directory is a test that edits the evidence.
`test_gpu_parity` used to drop `parity_fp16.json` straight into
`benchmarks/reports/`, so every `pytest tests` run silently rewrote a file that
critique documents cite by name and by sha256 -- found by the F9 cycle-15 critic,
which had to disclose that its own suite run had done it (F9_REPORT_C16, item 13).

The report is worth keeping, so the option stays; only the default moves. Without
`--parity-out` the report lands in the test's own `tmp_path` and disappears with
it; with it, the caller says out loud where it wants the file.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--parity-out",
        action="store",
        default=None,
        metavar="ARQUIVO",
        help=(
            "Onde gravar o relatorio de paridade fp16. Sem esta opcao ele vai para o "
            "tmp_path do teste, para que rodar a suite nao reescreva nada publicado."
        ),
    )


@pytest.fixture
def parity_out(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """The file `test_gpu_fp16_parity` writes its report to."""
    escolhido = request.config.getoption("--parity-out")
    if escolhido:
        destino = Path(escolhido)
        destino.parent.mkdir(parents=True, exist_ok=True)
        return destino
    return tmp_path / "parity_fp16.json"
