"""Regex search and substitution across a whole library, not one buffer.

:mod:`caissa.notation.regex_engine` already does the hard part -- PCRE over raw
text *and* over the move tree, scoping, per-match accept/reject, undo -- and it
does it well.  This module does not reimplement any of it.  What it adds is the
two things that only exist once there is an index:

**Reach.**  The engine searches a :class:`~caissa.notation.regex_engine.
SearchDocument`.  A user with 1,200 books has 1,200 of them, and running a
regex over all of it is minutes.  Here the index narrows first -- FTS,
facets, position -- and the engine runs on what survives.  A pattern with a
literal in it therefore costs a B-tree lookup plus a few hundred small regex
runs instead of a linear pass over gigabytes.

**Durability.**  ``SubstitutionPlan.apply`` returns an undo token that lives in
memory.  A corpus-wide replace touches hundreds of files and the user closes
the application; an undo that does not survive that is not an undo.  Every
applied edit is journalled in the index (``edit_journal``), so
:meth:`CorpusRegex.undo` works tomorrow.

**What this refuses to do.**  A node whose text is not stored in the index --
a PGN game, which is a byte range in a file the user owns -- is *not* rewritten
here.  Editing it means rewriting a multi-gigabyte file in place, which is the
PDF-writing front's problem and not a search engine's.  Such nodes are reported
in :attr:`CorpusSubstitutionResult.skipped` with the reason, never silently
dropped and never silently mangled.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from caissa.index.errors import QueryError
from caissa.index.query import Hit, Query, SearchIndex
from caissa.index.schema import transaction
from caissa.index.text_index import TextIndex
from caissa.index.tokenizer import ChessTokenizer
from caissa.notation.regex_engine import (
    Match,
    PlannedEdit,
    RegexEngine,
    Scope,
    SearchDocument,
    SubstitutionPlan,
)

__all__ = [
    "CorpusRegex",
    "CorpusSubstitutionPlan",
    "CorpusSubstitutionResult",
    "NodeEdits",
]


@dataclass(slots=True)
class NodeEdits:
    """One node's worth of a corpus-wide substitution.

    Wraps the engine's own :class:`~caissa.notation.regex_engine.
    SubstitutionPlan` rather than copying its accept/reject logic, so per-match
    behaviour is identical whether the user is editing one document or the whole
    library.
    """

    node_id: int
    doc_id: int
    uri: str
    title: str
    page: int
    node_ulid: str
    scope: Scope
    plan: SubstitutionPlan
    editable: bool = True
    """``False`` when the node's text lives in the source file, not the index."""

    def __len__(self) -> int:
        return len(self.plan)

    def preview(self) -> str:
        """Every match with its replacement, as the engine renders it."""
        return self.plan.preview()


@dataclass(slots=True)
class CorpusSubstitutionPlan:
    """Everything a pattern would change, across every document, applied to none.

    The contract SPEC 9 asks for: "substituição pré-visualizada", per-match
    accept or reject, and nothing written until :meth:`CorpusRegex.apply`.
    """

    pattern: str
    replacement: str
    nodes: list[NodeEdits] = field(default_factory=list)
    batch: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __len__(self) -> int:
        """How many individual matches the plan holds."""
        return sum(len(node) for node in self.nodes)

    @property
    def documents(self) -> int:
        """How many distinct documents are touched."""
        return len({node.doc_id for node in self.nodes})

    @property
    def accepted(self) -> int:
        """How many matches are currently marked for application."""
        return sum(len(node.plan.accepted) for node in self.nodes)

    def matches(self) -> Iterator[tuple[NodeEdits, int, PlannedEdit]]:
        """Every planned edit with the node it belongs to and its index in it."""
        for node in self.nodes:
            for index, edit in enumerate(node.plan):
                yield (node, index, edit)

    def accept(self, node_id: int, index: int) -> None:
        """Mark one match for application."""
        self._node(node_id).plan.accept(index)

    def reject(self, node_id: int, index: int) -> None:
        """Exclude one match."""
        self._node(node_id).plan.reject(index)

    def accept_all(self) -> None:
        """Mark every match."""
        for node in self.nodes:
            node.plan.accept_all()

    def reject_all(self) -> None:
        """Exclude every match -- the safe starting point for a risky pattern."""
        for node in self.nodes:
            node.plan.reject_all()

    def preview(self) -> str:
        """A human-readable diff of the whole plan, document by document."""
        lines: list[str] = []
        for node in self.nodes:
            where = f"{node.title or node.uri}"
            if node.page >= 0:
                where += f", pagina {node.page}"
            flag = "" if node.editable else "  [somente leitura: texto no arquivo de origem]"
            lines.append(f"--- {where} ({node.scope}){flag}")
            lines.append(node.preview())
        return "\n".join(lines)

    def _node(self, node_id: int) -> NodeEdits:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        msg = f"no {node_id} nao faz parte deste plano"
        raise QueryError(msg)


@dataclass(frozen=True, slots=True)
class CorpusSubstitutionResult:
    """What :meth:`CorpusRegex.apply` actually did."""

    batch: str
    nodes_changed: int
    edits_applied: int
    skipped: tuple[tuple[int, str], ...] = ()
    """``(node_id, reason)`` for every node that was not written."""

    @property
    def can_undo(self) -> bool:
        """Whether :meth:`CorpusRegex.undo` has anything to restore."""
        return self.nodes_changed > 0


class CorpusRegex:
    """Regex search and substitution over an indexed library.

    Args:
        index: The writable index.  Substitution needs it; search alone would
            be happy with a reader, but keeping one object avoids two ways to
            open the same file.
    """

    def __init__(self, index: TextIndex) -> None:
        self._index = index
        self._reader = SearchIndex.wrap(index.connection, tokenizer=index.tokenizer)
        self._engine = RegexEngine()

    @property
    def tokenizer(self) -> ChessTokenizer:
        """The tokenizer the index was built with."""
        return self._index.tokenizer

    # -- search ----------------------------------------------------------- #

    def search(
        self,
        pattern: str,
        *,
        query: Query | None = None,
        limit: int = 200,
    ) -> list[Hit]:
        r"""Every match of ``pattern`` in the corpus ``query`` selects.

        Args:
            pattern: A PCRE pattern.  Named groups, lookaround and
                ``\\p{...}`` all work when the ``regex`` package is installed;
                :data:`caissa.notation.regex_engine.PCRE` says whether it is.
            query: Narrows what is searched.  Its ``scope`` restricts to
                captions, comments, moves and so on -- the scoping SPEC 9 asks
                for, applied across the whole library rather than one file.
            limit: Maximum hits.

        Returns:
            Hits in document order, each with the offsets of the match inside
            its node's text.
        """
        base = query or Query()
        found: list[Hit] = []
        page = self._reader.search(
            Query(
                text=base.text,
                match=base.match,
                regex=None,
                scope=base.scope,
                move=base.move,
                position=base.position,
                position_pattern=base.position_pattern,
                material=base.material,
                eco=base.eco,
                player=base.player,
                year_min=base.year_min,
                year_max=base.year_max,
                annotation=base.annotation,
                documents=base.documents,
                stratum=base.stratum,
                include_collisions=base.include_collisions,
                limit=limit,
                offset=0,
            )
        )
        for hit in page.hits:
            document = self._document_for(hit)
            for match in self._engine.search(pattern, document, scope=base.scope, limit=limit):
                found.append(_rehit(hit, match))
                if len(found) >= limit:
                    return found
        return found

    # -- substitution ----------------------------------------------------- #

    def plan(
        self,
        pattern: str,
        replacement: str,
        *,
        query: Query | None = None,
        limit: int = 5_000,
    ) -> CorpusSubstitutionPlan:
        r"""Build the plan for ``pattern`` -> ``replacement``, writing nothing.

        Args:
            pattern: The PCRE pattern.
            replacement: The template.  ``\\g<name>`` and ``\\1`` expand per
                match, which is why the preview can show the real replacement
                text for every hit rather than the template.
            query: Narrows the corpus, including by scope.
            limit: Maximum nodes to plan over.  A plan is a thing a human
                reviews; an unbounded one is not reviewable.

        Returns:
            A :class:`CorpusSubstitutionPlan` with every match accepted, which
            is the engine's own default and matches what a user expects from a
            "replace all" they are about to inspect.
        """
        base = query or Query()
        scope = base.scope
        page = self._reader.search(
            Query(
                text=base.text,
                match=base.match,
                scope=scope,
                documents=base.documents,
                stratum=base.stratum,
                player=base.player,
                year_min=base.year_min,
                year_max=base.year_max,
                eco=base.eco,
                limit=limit,
                offset=0,
            )
        )
        plan = CorpusSubstitutionPlan(pattern=pattern, replacement=replacement)
        for hit in page.hits:
            document = self._document_for(hit)
            node_plan = self._engine.plan_substitution(pattern, replacement, document, scope=scope)
            if not len(node_plan):
                continue
            plan.nodes.append(
                NodeEdits(
                    node_id=hit.node_id,
                    doc_id=hit.doc_id,
                    uri=hit.uri,
                    title=hit.title,
                    page=hit.page,
                    node_ulid=hit.node_ulid,
                    scope=hit.scope,
                    plan=node_plan,
                    editable=self._is_editable(hit.node_id),
                )
            )
        return plan

    def apply(
        self,
        plan: CorpusSubstitutionPlan,
        *,
        on_write: Callable[[str, str, str, str], None] | None = None,
    ) -> CorpusSubstitutionResult:
        """Apply the accepted matches, journalling every change for undo.

        Args:
            plan: The reviewed plan.
            on_write: Called as ``(uri, node_ulid, before, after)`` for each
                changed node, so the editor can push the change into the
                document itself.  The index is the search copy; the document is
                the truth, and this is the seam between them.

        Returns:
            A :class:`CorpusSubstitutionResult`.  Nodes that could not be
            written appear in its ``skipped`` list with the reason.
        """
        changed = 0
        applied = 0
        skipped: list[tuple[int, str]] = []
        stamp = datetime.now(UTC).isoformat(timespec="seconds")

        with transaction(self._index.connection):
            for node in plan.nodes:
                if not node.plan.accepted:
                    continue
                if not node.editable:
                    skipped.append((node.node_id, "texto vive no arquivo de origem, nao no indice"))
                    continue
                before = node.plan.text
                result = node.plan.apply()
                after = result.text
                if after == before:
                    continue
                self._rewrite(node.node_id, after)
                self._index.connection.execute(
                    "INSERT INTO edit_journal(batch, doc_id, node_id, before, after, applied_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (plan.batch, node.doc_id, node.node_id, before, after, stamp),
                )
                changed += 1
                applied += len(node.plan.accepted)
                if on_write is not None:
                    on_write(node.uri, node.node_ulid, before, after)

        return CorpusSubstitutionResult(
            batch=plan.batch,
            nodes_changed=changed,
            edits_applied=applied,
            skipped=tuple(skipped),
        )

    def undo(
        self,
        batch: str,
        *,
        on_write: Callable[[str, str, str, str], None] | None = None,
    ) -> int:
        """Restore every node a batch changed.  Returns how many were restored.

        Exact restoration, not a reverse substitution: the journal holds the
        text as it was, so a pattern that was not invertible -- most of them --
        still undoes cleanly.
        """
        rows = self._index.connection.execute(
            "SELECT edit_id, node_id, before FROM edit_journal "
            "WHERE batch = ? AND undone = 0 ORDER BY edit_id DESC",
            (batch,),
        ).fetchall()
        if not rows:
            return 0
        restored = 0
        with transaction(self._index.connection):
            for row in rows:
                node_id = int(row[1])
                before = str(row[2])
                after = self._current_text(node_id)
                self._rewrite(node_id, before)
                self._index.connection.execute(
                    "UPDATE edit_journal SET undone = 1 WHERE edit_id = ?", (int(row[0]),)
                )
                restored += 1
                if on_write is not None:
                    uri, ulid = self._locate(node_id)
                    on_write(uri, ulid, after, before)
        return restored

    def batches(self) -> list[tuple[str, str, int]]:
        """``(batch, applied_at, nodes)`` for every batch that can still be undone."""
        rows = self._index.connection.execute(
            "SELECT batch, min(applied_at), count(*) FROM edit_journal WHERE undone = 0 "
            "GROUP BY batch ORDER BY min(applied_at) DESC"
        ).fetchall()
        return [(str(row[0]), str(row[1]), int(row[2])) for row in rows]

    # -- internals -------------------------------------------------------- #

    def _document_for(self, hit: Hit) -> SearchDocument:
        """A node's text as a :class:`SearchDocument`.

        The node is already scoped -- the index recorded which kind of thing it
        is -- so the whole node is one region of that scope.  Re-deriving
        regions by parsing here would throw away exactly the classification the
        IR gave us for free.
        """
        text = hit.text or self._reader.text_of(hit.node_id)
        from caissa.notation.regex_engine import Region

        regions = () if hit.scope is Scope.ALL else (Region(hit.scope, 0, len(text)),)
        return SearchDocument(text=text, regions=regions)

    def _is_editable(self, node_id: int) -> bool:
        row = self._index.connection.execute(
            "SELECT length(text) FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return row is not None and int(row[0] or 0) > 0

    def _current_text(self, node_id: int) -> str:
        row = self._index.connection.execute(
            "SELECT text FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return str(row[0]) if row is not None else ""

    def _locate(self, node_id: int) -> tuple[str, str]:
        row = self._index.connection.execute(
            "SELECT d.uri, n.node_ulid FROM nodes n JOIN documents d ON d.doc_id = n.doc_id "
            "WHERE n.node_id = ?",
            (node_id,),
        ).fetchone()
        return (str(row[0]), str(row[1])) if row is not None else ("", "")

    def _rewrite(self, node_id: int, text: str) -> None:
        """Replace a node's text and its postings, inside the caller's transaction."""
        connection: sqlite3.Connection = self._index.connection
        connection.execute("UPDATE nodes SET text = ? WHERE node_id = ?", (text, node_id))
        connection.execute("DELETE FROM nodes_fts WHERE rowid = ?", (node_id,))
        connection.execute(
            "INSERT INTO nodes_fts(rowid, tokens) VALUES (?, ?)",
            (node_id, self.tokenizer.encode(text)),
        )


def _rehit(hit: Hit, match: Match) -> Hit:
    """The same hit, pointing at one specific match inside it."""
    return Hit(
        doc_id=hit.doc_id,
        uri=hit.uri,
        title=hit.title,
        node_id=hit.node_id,
        node_ulid=hit.node_ulid,
        scope=hit.scope,
        page=hit.page,
        text=hit.text,
        start=match.start,
        end=match.end,
        score=hit.score,
        snippet=match.context(hit.text),
        groups=dict(match.groups),
        position_exact=hit.position_exact,
        collisions=hit.collisions,
    )


def scope_names() -> Sequence[str]:
    """Every scope a search can be restricted to, for a UI menu."""
    return tuple(str(scope) for scope in Scope)
