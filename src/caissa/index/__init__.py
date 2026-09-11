"""Index and search for large chess libraries -- front F10, SPEC 9, ADR-0007.

The user's own description of the problem: "bases de dados de xadrez de vários
tamanhos de gigas e uma quantidade gigante de pdf", plus "recursos de Regex".
This package is that request.

What was already there and is *not* rewritten here
--------------------------------------------------

``ChessVisionOFF_Puro/src/chess_diagram_ocr/games_db.py`` and friends already
search a 18.9 GB PGN collection by player and by position, and their inverted
design -- hold the wanted positions in memory, stream the base past them -- is
the right answer for a giant third-party file (``ASSETS.md`` 2.7).  Nothing here
replaces it.

``caissa.notation.regex_engine`` already implements SPEC 9's regex engine over
one document: PCRE, scoping, move patterns, material signatures, board patterns,
per-match preview and undo.  Nothing here reimplements it either;
:mod:`caissa.index.corpus_regex` calls it.

What is new
-----------

:mod:`~caissa.index.tokenizer`
    The FTS5 tokenizer that keeps ``O-O-O``, ``1.e4``, ``Qxd5+`` and ``♘f3``
    searchable, and keeps ``Bxc4`` distinct from ``bxc4`` despite SQLite's
    unavoidable case folding.  ADR-0007 called this the part that has to be got
    right; it is the crux of the front.
:mod:`~caissa.index.text_index`
    Full-text indexing over the Document IR, incremental by fingerprint,
    resumable by cursor, bounded by ``cache.index_budget_gb``.
:mod:`~caissa.index.position_index`
    A Zobrist B-tree over positions, so "which of my 1,200 PDFs contains this?"
    is a lookup instead of a scan -- with hash collisions surfaced rather than
    resolved by luck.
:mod:`~caissa.index.query`
    The single entry point, combining text, regex, scope, move pattern,
    material, position and facets into one ranked, paginated answer with enough
    provenance to jump to the page and node.
:mod:`~caissa.index.corpus_regex`
    The notation engine's substitution, extended to a whole library and given a
    journal so undo survives closing the application.
:mod:`~caissa.index.background`
    One writer thread, real progress, a cancel that keeps its work.

Typical use::

    from caissa.index import PgnSource, Query, SearchIndex, TextIndex

    with TextIndex(path) as index:
        index.add(PgnSource(Path("studies.pgn")))

    with SearchIndex(path) as search:
        page = search.search(Query(text="O-O-O", scope=Scope.COMMENTS))
"""

from __future__ import annotations

from caissa.index.background import BackgroundIndexer, Progress
from caissa.index.corpus_regex import (
    CorpusRegex,
    CorpusSubstitutionPlan,
    CorpusSubstitutionResult,
    NodeEdits,
)
from caissa.index.errors import (
    BudgetExceededError,
    IndexBackendError,
    IndexCorruptError,
    IndexMissingError,
    IndexStaleError,
    QueryError,
)
from caissa.index.position_index import PositionHit, PositionLookup, PositionQuery
from caissa.index.query import Hit, Query, ResultPage, SearchIndex
from caissa.index.schema import SCHEMA_VERSION, connect, database_bytes
from caissa.index.sources import (
    Facets,
    IndexUnit,
    IrSource,
    PdfTextSource,
    PgnSource,
    PositionRef,
    Source,
    TextSource,
)
from caissa.index.text_index import (
    DocumentRow,
    IndexReport,
    IndexStats,
    TextIndex,
    index_all,
    open_index,
)
from caissa.index.tokenizer import (
    FTS5_TOKENIZE,
    TOKENIZER_VERSION,
    ChessTokenizer,
    decode_token,
    encode_case,
    is_notation,
)
from caissa.index.zobrist import (
    ZOBRIST_VERSION,
    hash_placement,
    pack_placement,
    unpack_placement,
)

__all__ = [
    "FTS5_TOKENIZE",
    "SCHEMA_VERSION",
    "TOKENIZER_VERSION",
    "ZOBRIST_VERSION",
    "BackgroundIndexer",
    "BudgetExceededError",
    "ChessTokenizer",
    "CorpusRegex",
    "CorpusSubstitutionPlan",
    "CorpusSubstitutionResult",
    "DocumentRow",
    "Facets",
    "Hit",
    "IndexBackendError",
    "IndexCorruptError",
    "IndexMissingError",
    "IndexReport",
    "IndexStaleError",
    "IndexStats",
    "IndexUnit",
    "IrSource",
    "NodeEdits",
    "PdfTextSource",
    "PgnSource",
    "PositionHit",
    "PositionLookup",
    "PositionQuery",
    "PositionRef",
    "Progress",
    "Query",
    "QueryError",
    "ResultPage",
    "SearchIndex",
    "Source",
    "TextIndex",
    "TextSource",
    "connect",
    "database_bytes",
    "decode_token",
    "encode_case",
    "hash_placement",
    "index_all",
    "is_notation",
    "open_index",
    "pack_placement",
    "unpack_placement",
]
