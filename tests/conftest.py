"""Shared fixtures.

Every test runs against a hermetic configuration: the user file, the project
file and any ``CAISSA_*`` variable inherited from the developer's shell are
disabled, and the process-wide singletons in ``caissa.core.config``,
``caissa.vision.runtime.device`` and ``caissa.vision.runtime.residency`` are
reset before and after each test. Without this a stray ``caissa.toml`` on the
machine would silently change assertions.
"""

from __future__ import annotations

import os

import pytest

from caissa.core.config import load_config, reset_config, set_config
from caissa.vision.runtime.device import reset_device_cache
from caissa.vision.runtime.residency import reset_residency_manager


def _reset_all() -> None:
    reset_residency_manager()
    reset_device_cache(forget_torch=True)
    reset_config()


@pytest.fixture(autouse=True)
def hermetic_environment(monkeypatch):
    """Isolate every test from the developer's machine configuration."""
    for name in list(os.environ):
        if name.startswith("CAISSA_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CAISSA_NO_USER_CONFIG", "1")
    monkeypatch.setenv("CAISSA_NO_PROJECT_CONFIG", "1")

    _reset_all()
    set_config(load_config(env=dict(os.environ)))
    yield
    _reset_all()


@pytest.fixture
def empty_env() -> dict[str, str]:
    """An environment mapping with no Caissa variables at all."""
    return {}


# --------------------------------------------------------------------------- #
# Quem adianta o relogio dos ULID
# --------------------------------------------------------------------------- #
#
# `tests/unit/model/test_ids.py::test_a_fresh_id_carries_roughly_the_current_time`
# falhou **uma vez** numa execucao de `tests/unit` e passou na seguinte, com o mesmo
# comando e a mesma ordem (nao ha `pytest-randomly` instalado). Passa isolado e passa
# com `tests/unit/model` inteiro.
#
# O mecanismo esta reproduzido: `ids.py:82` faz
# `timestamp_ms = max(timestamp_ms, _last_timestamp_ms)` para garantir monotonicidade, e
# por isso o relogio do modulo **nunca volta**. Empurrado uma hora a frente, toda chamada
# seguinte herda a deriva e nao se recupera.
#
# O que falta e o **gatilho**. Rajada nao causa (300.000 ids seguidos dao 0 ms de deriva,
# porque a aleatoriedade e de 80 bits e o ramo de estouro quase nunca dispara), e os dois
# testes que mexem no relogio salvam e restauram o estado sob lock.
#
# Este gancho nomeia o culpado na proxima vez em vez de deixar supor: ele mede a deriva
# depois de **cada** teste e falha no ato, apontando o teste, quando ela passa de
# `_DERIVA_TOLERADA_MS`. Sem ele, a proxima ocorrencia volta a ser um misterio a 11 minutos
# de distancia da causa.

_DERIVA_TOLERADA_MS = 5_000


@pytest.fixture(autouse=True)
def _vigiar_o_relogio_dos_ulid(request: pytest.FixtureRequest):
    """Falha no teste que empurrar `ids._last_timestamp_ms` para o futuro."""
    yield
    try:
        from caissa.core.model import ids
    except Exception:  # noqa: BLE001 - um teste pode estar medindo a ausencia do pacote
        return
    with ids._MONOTONIC_LOCK:
        marcado = ids._last_timestamp_ms
    if marcado <= 0:
        return
    import time as _time

    deriva = marcado - int(_time.time() * 1000.0)
    if deriva > _DERIVA_TOLERADA_MS:
        with ids._MONOTONIC_LOCK:
            ids._last_timestamp_ms = 0
            ids._last_randomness = 0
        pytest.fail(
            f"{request.node.nodeid} deixou o relogio dos ULID {deriva} ms no futuro "
            f"(tolerancia {_DERIVA_TOLERADA_MS} ms). O grampo de monotonicidade de "
            f"ids.py:82 nunca volta, entao todo id seguinte herdaria a deriva -- e e assim "
            f"que test_a_fresh_id_carries_roughly_the_current_time reprova. O estado foi "
            f"zerado para nao contaminar o resto da suite."
        )
