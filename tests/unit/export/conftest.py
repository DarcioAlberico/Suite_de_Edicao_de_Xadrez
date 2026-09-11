"""Fixtures for the exporter tests.

The corpus these tests measure against is the *same* one the IR tests use --
``tests/unit/model/generators.py``. That is deliberate: an exporter that only
survives documents its own author thought of is an exporter that has not been
tested. Putting the model test directory on ``sys.path`` is what lets
``from generators import NodeFactory`` work here too; putting this directory on
it is what lets ``from corpus import FORMATS`` work regardless of how pytest
was invoked.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MODEL_TESTS = _HERE.parent / "model"
for _path in (str(_HERE), str(_MODEL_TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import pytest  # noqa: E402
from corpus import CORPUS_NODES, CORPUS_SEED  # noqa: E402
from generators import NodeFactory  # noqa: E402

from caissa.core.model import Document  # noqa: E402


@pytest.fixture(scope="session")
def factory() -> NodeFactory:
    """A node factory seeded so the whole session sees one corpus."""
    return NodeFactory(CORPUS_SEED)


@pytest.fixture(scope="session")
def corpus(factory: NodeFactory) -> Document:
    """A document exercising every node type and every run property."""
    return factory.document(min_nodes=CORPUS_NODES)


@pytest.fixture
def small() -> Document:
    """A smaller document, for tests that only need something structural."""
    return NodeFactory(7).document(min_nodes=40)
