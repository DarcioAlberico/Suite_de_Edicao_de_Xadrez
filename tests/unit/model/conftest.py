"""Fixtures for the Document IR tests.

The synthetic node factory lives beside these modules in ``generators.py``
rather than in ``src``: it is test scaffolding, not product code. Putting this
directory on ``sys.path`` is what lets every test module say
``from generators import NodeFactory`` regardless of how pytest was invoked.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pytest  # noqa: E402
from generators import NodeFactory  # noqa: E402

#: Seed for every generated corpus. Printed in assertion messages so a failure
#: is reproducible from the seed alone.
CORPUS_SEED = 0xCA155A

#: Node count the F1 acceptance gate demands of the round-trip corpus.
CORPUS_NODES = 10_000


@pytest.fixture(scope="session")
def factory() -> NodeFactory:
    """A node factory seeded so that the whole session sees one corpus."""
    return NodeFactory(CORPUS_SEED)
