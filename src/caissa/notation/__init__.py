"""Chess notation: grammar, multilingual rendering, repair and search (front F6).

Two mature implementations were absorbed here on 2026-09-07 rather than
rewritten (``docs/ASSETS.md`` 5, 6).  Each file carries an ``# Origem:`` header
saying where it came from and what changed.

``PGN_Live_Editor/pgn_live_editor/core/`` -- 21 modules, Qt-free, 93% covered.
    The tolerant parser and everything around it: :mod:`~caissa.notation.tokenizer`,
    :mod:`~caissa.notation.parser`, :mod:`~caissa.notation.candidates`,
    :mod:`~caissa.notation.substitutions`, :mod:`~caissa.notation.normalizer`,
    :mod:`~caissa.notation.nag_table`, :mod:`~caissa.notation.book_import`.
    Its defining property is that it *never fails*: every token becomes either a
    move, a comment or a visible :class:`~caissa.notation.issues.Issue`, and a
    move is never lost in silence.

``ChessVisionOFF_Puro/src/chess_diagram_ocr/text/notacao.py``
    The prose-versus-move discriminator.  Its conservative "a slice is notation
    only if a majority of its tokens are, and at least one is a real move" rule
    is reproduced by :func:`~caissa.notation.legality_repair._is_move_like` and
    by the tokenizer's ``NOTATION_NEIGHBOURS`` context rule.

Built new on top:

:mod:`~caissa.notation.languages`
    Eight notation locales plus figurines, exact SAN round-tripping, and a
    scored language detector that **abstains** instead of guessing.
:mod:`~caissa.notation.legality_repair`
    SPEC 7.3 / ADR-0008: OCR repair whose candidate space is the legal-move set
    of the current position, verified by replaying the whole game.
:mod:`~caissa.notation.regex_engine`
    SPEC 9: PCRE search over raw text *and* the move tree, chess-aware query
    primitives, and substitution with per-match preview and undo.
"""

from __future__ import annotations

from .candidates import CandidateResolver, looks_like_move
from .issues import Candidate, Issue
from .languages import (
    LOCALES,
    Detection,
    NotationLocale,
    detect_language,
    figurine,
    from_language,
    get_locale,
    to_language,
)
from .legality_repair import LegalityRepairer, RepairReport, repair_movetext
from .normalizer import LiveTextNormalizer
from .parser import GameAST, MoveNode, TolerantParser, iter_moves
from .regex_engine import (
    AnnotationQuery,
    EcoQuery,
    MaterialSignature,
    MoveQuery,
    PositionPattern,
    RegexEngine,
    Scope,
    SearchDocument,
    SubstitutionPlan,
    UndoStack,
    document_from_ast,
)
from .substitutions import Dictionary, Substitution
from .tokenizer import PGNTokenizer

__all__ = [
    "LOCALES",
    "AnnotationQuery",
    "Candidate",
    "CandidateResolver",
    "Detection",
    "Dictionary",
    "EcoQuery",
    "GameAST",
    "Issue",
    "LegalityRepairer",
    "LiveTextNormalizer",
    "MaterialSignature",
    "MoveNode",
    "MoveQuery",
    "NotationLocale",
    "PGNTokenizer",
    "PositionPattern",
    "RegexEngine",
    "RepairReport",
    "Scope",
    "SearchDocument",
    "Substitution",
    "SubstitutionPlan",
    "TolerantParser",
    "UndoStack",
    "detect_language",
    "document_from_ast",
    "figurine",
    "from_language",
    "get_locale",
    "iter_moves",
    "looks_like_move",
    "repair_movetext",
    "to_language",
]
