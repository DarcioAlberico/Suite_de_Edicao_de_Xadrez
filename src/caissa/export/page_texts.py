"""The trunk's corrected pages, in place of the import's reading, before a book is written.

The trunk (ChessVisionOFF) corrects a book page by page in its *Texto* tab and keeps every
corrected page in a notebook of its own (its ``text/caderno.py``, S-610).  *Exportar o livro
para EPUB…/DOCX…* wrote the suite's reading of the same pages, so an afternoon of corrections
never reached the book (the trunk's ``docs/ROADMAP_MESA_DE_TEXTO.md``, R7).

What crosses is plain data -- a list of dicts, version :data:`FORMAT` -- because neither package
imports the other: in a checkout the suite runs on its own Python.  :meth:`PageText.from_dict`
reads it, and :func:`apply_page_texts` is the same move as
:func:`caissa.export.book.apply_diagram_decisions`: the import, with the person's work applied
to the pages it covers.

**The rule, per corrected page.**

* The page's **text** goes: every top-level :class:`Paragraph`, :class:`Heading` and
  :class:`GameScore` whose provenance places it on the page, the image of a page the import
  could not read (a bare :class:`ImageBlock` of kind ``IMAGE`` with no confidence), and the
  figure of an abstained OCR region (``note`` starting with ``"OCR abstido"``).  The notebook
  holds what those said, read and corrected.
* The page's **pictures** stay -- diagrams, figures -- in their order, and each diagram mark
  of the notebook takes the next one, so the diagram lands between the paragraphs where the
  person sees it.  What no mark took follows the page's text.
* The new blocks take the place of the page's first block, or follow the previous page's last
  one when the import had nothing on the page.

A paragraph the import joined across two pages belongs to its first page; replacing that page
drops the continuation, and :attr:`PageTextsApplied.notes` says so -- it is the one loss the
rule makes, and saying it is what keeps it from being silent.

**And the way back** (:func:`page_texts_of`, the trunk's R7 de volta): the pages of an import
written in the same format, so the corrections made in the *Revisão de texto* window reach the
trunk's notebook.  The page's paragraphs, headings and scores in order, each diagram as a mark
with its position; emphasis, style and alignment as above, read back.  Who decides which pages go
and how the import got the decisions is :mod:`caissa.export.reviewed_pages`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final

from caissa.core.model import (
    Alignment,
    Block,
    Diagram,
    Document,
    Emphasis,
    Figure,
    GameScore,
    Heading,
    ImageBlock,
    Paragraph,
    ParagraphProps,
    Provenance,
    RunProps,
    SourceKind,
    StrikeStyle,
    Strong,
    Text,
    UnderlineStyle,
    inline_children,
    plain_text,
)
from caissa.ingest.pdf import ImportResult

__all__ = [
    "FORMAT",
    "PageText",
    "PageTextsApplied",
    "TextParagraph",
    "TextRun",
    "apply_page_texts",
    "page_text_of",
    "page_texts_from",
    "page_texts_of",
]

FORMAT: Final = 1
"""The version of the data the trunk sends (its ``text/caderno_na_suite.FORMATO``)."""

_STYLES: Final[dict[str, str]] = {
    "": "Body",
    "heading": "Heading 1",
    "notation": "Movetext",
    "caption": "Caption",
}
_ALIGNMENTS: Final[dict[str, Alignment]] = {
    "left": Alignment.LEFT,
    "center": Alignment.CENTER,
    "right": Alignment.RIGHT,
    "justify": Alignment.JUSTIFY,
}
_JOINED: Final = "continua até a página"
"""What the importer writes in ``provenance.note`` of a paragraph joined across pages."""


@dataclass(frozen=True, slots=True)
class TextRun:
    """A stretch of one paragraph with one emphasis."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False

    def props(self) -> RunProps:
        return RunProps(
            font_weight=700 if self.bold else None,
            italic=True if self.italic else None,
            underline=UnderlineStyle.SINGLE if self.underline else None,
            strikethrough=StrikeStyle.SINGLE if self.strike else None,
        )


@dataclass(frozen=True, slots=True)
class TextParagraph:
    """A paragraph of the page, or the mark of where one of its diagrams goes."""

    kind: str = "text"
    """``"text"`` or ``"diagram"``."""
    runs: tuple[TextRun, ...] = ()
    style: str = ""
    """``"heading"``, ``"notation"``, ``"caption"`` or ``""`` (body)."""
    alignment: str = ""
    fen: str = ""
    """For a diagram mark: the placement the trunk read, or ``""``.  Informative only."""

    @property
    def is_diagram(self) -> bool:
        return self.kind == "diagram"


@dataclass(frozen=True, slots=True)
class PageText:
    """One corrected page of the trunk's notebook (zero-based ``page_index``)."""

    page_index: int
    paragraphs: tuple[TextParagraph, ...] = ()
    state: str = ""
    """``"editada"`` or ``"conferida"``, the notebook's words."""
    saved_at: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PageText:
        """Read one page; ``ValueError`` for a format this suite does not know."""
        version = data.get("format", FORMAT)
        if version != FORMAT:
            raise ValueError(f"formato de folha do caderno desconhecido: {version!r}")
        paragraphs = []
        for item in data.get("paragraphs", ()):
            kind = str(item.get("kind", "text"))
            if kind not in ("text", "diagram"):
                raise ValueError(f"parágrafo de tipo desconhecido: {kind!r}")
            runs = tuple(
                TextRun(
                    text=str(run.get("text", "")),
                    bold=bool(run.get("bold", False)),
                    italic=bool(run.get("italic", False)),
                    underline=bool(run.get("underline", False)),
                    strike=bool(run.get("strike", False)),
                )
                for run in item.get("runs", ())
            )
            paragraphs.append(
                TextParagraph(
                    kind=kind,
                    runs=runs,
                    style=str(item.get("style", "")),
                    alignment=str(item.get("alignment", "")),
                    fen=str(item.get("fen", "")),
                )
            )
        return cls(
            page_index=int(data["page_index"]),
            paragraphs=tuple(paragraphs),
            state=str(data.get("state", "")),
            saved_at=str(data.get("saved_at", "")),
        )


def page_texts_from(items: Iterable[PageText | Mapping[str, Any]]) -> dict[int, PageText]:
    """The pages by index; a later page with the same index replaces the earlier one."""
    pages: dict[int, PageText] = {}
    for item in items:
        page = item if isinstance(item, PageText) else PageText.from_dict(item)
        pages[page.page_index] = page
    return pages


@dataclass(frozen=True, slots=True)
class PageTextsApplied:
    """What :func:`apply_page_texts` did, besides the counter in the report."""

    imported: ImportResult
    pages: tuple[int, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)
    """One line per loss, one-based page first, in Portuguese for the status bar."""


def _page_of(block: Block) -> int | None:
    provenance = getattr(block, "provenance", None)
    source = block.source if isinstance(block, Diagram) else None
    if source is not None and source.page_index is not None:
        return int(source.page_index)
    if provenance is None or provenance.page_index is None:
        return None
    return int(provenance.page_index)


def _is_text(block: Block) -> bool:
    """A block whose words the notebook holds -- the ones that go."""
    if isinstance(block, (Paragraph, Heading, GameScore)):
        return True
    provenance = getattr(block, "provenance", None)
    note = (provenance.note or "") if provenance is not None else ""
    if isinstance(block, ImageBlock):
        # The image of a page the import did not read (`_scan_node`): a figure has a Figure.
        return provenance is not None and provenance.kind is SourceKind.IMAGE and not (
            provenance.confidence
        )
    if isinstance(block, Figure):
        return note.startswith("OCR abstido")
    return False


def _paragraph(item: TextParagraph, provenance: Provenance) -> Block:
    content = tuple(Text(content=run.text, props=run.props()) for run in item.runs if run.text)
    props = ParagraphProps(
        style=_STYLES.get(item.style, "Body"), alignment=_ALIGNMENTS.get(item.alignment)
    )
    if item.style == "heading":
        return Heading(level=1, content=content, props=props, provenance=provenance)
    return Paragraph(content=content, props=props, provenance=provenance)


def _provenance(page: PageText, model: Provenance | None) -> Provenance:
    when = f" em {page.saved_at}" if page.saved_at else ""
    return Provenance(
        kind=SourceKind.HUMAN,
        document_path=model.document_path if model is not None else None,
        document_hash=model.document_hash if model is not None else None,
        page_index=page.page_index,
        engine="caderno",
        confidence=1.0,
        verified_by_human=True,
        note=f"corrigido no caderno da aba Texto{when}",
    )


def _new_blocks(
    page: PageText, kept: Sequence[Block], model: Provenance | None
) -> tuple[list[Block], int]:
    """The page as the notebook has it, with the kept pictures; and the marks left without one."""
    provenance = _provenance(page, model)
    queue = list(kept)
    blocks: list[Block] = []
    unmatched = 0
    for item in page.paragraphs:
        if not item.is_diagram:
            if any(run.text for run in item.runs):
                blocks.append(_paragraph(item, provenance))
            continue
        index = next((i for i, b in enumerate(queue) if isinstance(b, Diagram)), None)
        if index is None:
            unmatched += 1
            continue
        blocks.extend(queue[: index + 1])
        del queue[: index + 1]
    blocks.extend(queue)
    return blocks, unmatched


def _page_blocks(page: PageText, blocks: Sequence[Block]) -> tuple[list[Block], list[str]]:
    """The new blocks of one page, from its blocks in the import; and what they left out."""
    model = next((b.provenance for b in blocks if getattr(b, "provenance", None)), None)
    notes = [
        f"página {page.page_index + 1}: o parágrafo que seguia na página seguinte saiu com o "
        "texto do caderno, e a parte de lá ficou de fora"
        for block in blocks
        if _is_text(block) and _JOINED in (getattr(block.provenance, "note", None) or "")
    ]
    new, unmatched = _new_blocks(page, [b for b in blocks if not _is_text(b)], model)
    if unmatched:
        notes.append(
            f"página {page.page_index + 1}: {unmatched} diagrama(s) do caderno sem diagrama "
            "correspondente na importação"
        )
    return new, notes


def _insert_in_order(body: list[Block], index: int, new: Sequence[Block]) -> None:
    """``new`` (page ``index``) before the first block of a later page; the body is in page order."""
    pages = [_page_of(block) for block in body]
    later = (i for i, page in enumerate(pages) if page is not None and page > index)
    at = next(later, len(body))
    body[at:at] = new


def apply_page_texts(
    imported: ImportResult, page_texts: Iterable[PageText | Mapping[str, Any]]
) -> PageTextsApplied:
    """The import with the trunk's corrected pages in place of its reading of them.

    Pages the import did not build are ignored -- the export writes the pages asked for, and
    a corrected page outside them is not one of them.  **The report is not touched**: it is
    the very object of the window's import in hand, which the next export receives again, and
    a counter added to it would count the same pages twice.  The pages applied are
    :attr:`PageTextsApplied.pages`; with none, the import comes back as it was.
    """
    pages = page_texts_from(page_texts)
    built = {int(p.index) for p in getattr(imported.report, "pages", ())}
    body = tuple(imported.document.body)
    if not built:
        built = {p for p in (_page_of(b) for b in body) if p is not None}
    wanted = {index: page for index, page in pages.items() if index in built}
    if not wanted:
        return PageTextsApplied(imported=imported)

    by_page: dict[int, list[int]] = {}
    for position, block in enumerate(body):
        index = _page_of(block)
        if index in wanted:
            by_page.setdefault(index, []).append(position)

    notes: list[str] = []
    replacement: dict[int, list[Block]] = {}  # position of the first block -> the new blocks
    dropped: set[int] = set()
    appended: list[tuple[int, list[Block]]] = []  # pages the import had nothing on
    for index, page in sorted(wanted.items()):
        positions = by_page.get(index, [])
        new, page_notes = _page_blocks(page, [body[p] for p in positions])
        notes.extend(page_notes)
        if positions:
            replacement[positions[0]] = new
            dropped.update(positions[1:])
        else:
            appended.append((index, new))

    result: list[Block] = []
    for position, block in enumerate(body):
        if position in replacement:
            result.extend(replacement[position])
        elif position not in dropped:
            result.append(block)
    for index, new in appended:
        _insert_in_order(result, index, new)

    document: Document = replace(imported.document, body=tuple(result))
    return PageTextsApplied(
        imported=ImportResult(document=document, report=imported.report),
        pages=tuple(sorted(wanted)),
        notes=tuple(notes),
    )


# --------------------------------------------------------------------------- the way back


_STYLE_BACK: Final[dict[str, str]] = {name: key for key, name in _STYLES.items() if key}
_ALIGNMENT_BACK: Final[dict[Alignment, str]] = {value: key for key, value in _ALIGNMENTS.items()}
_BOLD_FROM: Final = 600
"""The weight from which a run reads back as bold: semibold and up, as the trunk draws it."""


def _emphasis(props: RunProps | None, inherited: dict[str, bool]) -> dict[str, bool]:
    marks = dict(inherited)
    if props is None:
        return marks
    if props.font_weight is not None and props.font_weight >= _BOLD_FROM:
        marks["bold"] = True
    if props.italic:
        marks["italic"] = True
    if props.underline not in (None, UnderlineStyle.NONE):
        marks["underline"] = True
    if props.strikethrough not in (None, StrikeStyle.NONE):
        marks["strike"] = True
    return marks


def _runs(nodes: Iterable[Any], inherited: dict[str, bool]) -> list[dict[str, Any]]:
    """The inlines as runs of one emphasis each; a move or a glyph reads as its text."""
    runs: list[dict[str, Any]] = []

    def add(text: str, marks: dict[str, bool]) -> None:
        if not text:
            return
        marks = {k: v for k, v in marks.items() if v}
        if runs and {k: v for k, v in runs[-1].items() if k != "text"} == marks:
            runs[-1]["text"] += text
        else:
            runs.append({"text": text, **marks})

    def walk(items: Iterable[Any], marks: dict[str, bool]) -> None:
        for node in items:
            if isinstance(node, Text):
                add(node.content, _emphasis(node.props, marks))
                continue
            inner = _emphasis(getattr(node, "props", None), marks)
            if isinstance(node, Emphasis):
                inner["italic"] = True
            elif isinstance(node, Strong):
                inner["bold"] = True
            children = inline_children(node)
            if children:
                walk(children, inner)
            else:
                add(plain_text((node,)), inner)

    walk(nodes, inherited)
    return runs


def _paragraph_dict(block: Paragraph | Heading) -> dict[str, Any] | None:
    props = block.props
    marks = _emphasis(getattr(block, "run_props", None), {})
    runs = _runs(block.content, marks)
    if not "".join(r["text"] for r in runs).strip():
        return None
    style = "heading" if isinstance(block, Heading) else _STYLE_BACK.get(props.style or "", "")
    alignment = _ALIGNMENT_BACK.get(props.alignment, "") if props.alignment is not None else ""
    return {"kind": "text", "style": style, "alignment": alignment, "runs": runs}


def page_text_of(
    imported: ImportResult, page_index: int, *, state: str = "editada", saved_at: str = ""
) -> dict[str, Any]:
    """One page of the import in the trunk's format: its text in order, its diagrams as marks.

    A score reads as its movetext, in the notation style -- the notebook has no game object, and
    the moves are what the page printed.  Pictures that are not diagrams stay out: the notebook
    holds words and diagram marks.
    """
    from caissa.export.text import game_to_pgn

    paragraphs: list[dict[str, Any]] = []
    for block in imported.document.body:
        if _page_of(block) != page_index:
            continue
        if isinstance(block, (Paragraph, Heading)):
            paragraph = _paragraph_dict(block)
            if paragraph is not None:
                paragraphs.append(paragraph)
        elif isinstance(block, GameScore):
            moves = game_to_pgn(block, include_headers=False).strip()
            if moves:
                paragraphs.append({"kind": "text", "style": "notation", "alignment": "",
                                   "runs": [{"text": moves}]})
        elif isinstance(block, Diagram):
            paragraphs.append({"kind": "diagram", "fen": block.fen, "alignment": ""})
    return {"format": FORMAT, "page_index": int(page_index), "state": state, "saved_at": saved_at,
            "paragraphs": paragraphs}


def page_texts_of(
    imported: ImportResult, pages: Iterable[int], *, saved_at: Mapping[int, str] | None = None
) -> list[dict[str, Any]]:
    """:func:`page_text_of` for each page the import built, in page order."""
    built = {int(p.index) for p in getattr(imported.report, "pages", ())}
    if not built:
        built = {p for p in (_page_of(b) for b in imported.document.body) if p is not None}
    when = saved_at or {}
    return [page_text_of(imported, index, saved_at=when.get(index, ""))
            for index in sorted({int(p) for p in pages} & built)]
