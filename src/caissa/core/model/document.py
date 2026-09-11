"""The ``Document`` root: metadata, stylesheet, resources and body (SPEC 5.1).

A document is the unit every importer produces and every exporter consumes. It
owns four things:

``metadata``
    Bibliographic facts, in a shape that maps cleanly onto Dublin Core (EPUB),
    XMP (PDF) and core properties (DOCX) without a lossy middle step.
``styles``
    The named, inheritable styles of :mod:`caissa.core.model.styles`.
``resources``
    Embedded fonts, images and stylesheets, referenced by key so the same font
    subset is embedded once no matter how many nodes use it.
``body``
    The block tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from caissa.core.chess.notation_tables import DEFAULT_LANGUAGE, FigurineSet, MoveRenderStyle
from caissa.core.model.base import IRNode
from caissa.core.model.blocks import Block
from caissa.core.model.registry import ir_node
from caissa.core.model.styles import StyleSheet

__all__ = [
    "Contributor",
    "ContributorRole",
    "Document",
    "DocumentMetadata",
    "DocumentSettings",
    "MetadataEntry",
    "Resource",
    "ResourceKind",
]


class ContributorRole(StrEnum):
    """MARC-style relator roles, the vocabulary EPUB and Dublin Core share."""

    AUTHOR = "author"
    EDITOR = "editor"
    TRANSLATOR = "translator"
    ILLUSTRATOR = "illustrator"
    ANNOTATOR = "annotator"
    COMPILER = "compiler"
    FOREWORD = "foreword"
    PUBLISHER = "publisher"
    CONTRIBUTOR = "contributor"
    DESIGNER = "designer"
    PHOTOGRAPHER = "photographer"


class ResourceKind(StrEnum):
    """What an embedded resource is."""

    FONT = "font"
    IMAGE = "image"
    STYLESHEET = "stylesheet"
    AUDIO = "audio"
    VIDEO = "video"
    DATA = "data"
    PGN = "pgn"


@ir_node("contributor")
@dataclass(frozen=True, slots=True, kw_only=True)
class Contributor:
    """A person or organisation credited on the document.

    Attributes:
        name: Display name, as it should be printed.
        role: What they contributed.
        sort_name: Name in sorting order, e.g. ``"Kasparov, Garry"``. EPUB
            calls this ``file-as`` and requires it for correct catalogues.
        identifier: A stable identifier such as an ORCID or a VIAF id.
    """

    name: str
    role: ContributorRole = ContributorRole.AUTHOR
    sort_name: str | None = None
    identifier: str | None = None


@ir_node("metadata_entry")
@dataclass(frozen=True, slots=True, kw_only=True)
class MetadataEntry:
    """One custom metadata field, kept as an ordered list to preserve source order.

    Attributes:
        name: Field name.
        value: Field value.
        scheme: Vocabulary the name belongs to, e.g. ``"dcterms"``.
    """

    name: str
    value: str
    scheme: str | None = None


@ir_node("resource")
@dataclass(frozen=True, slots=True, kw_only=True)
class Resource:
    """An embedded or referenced asset.

    Binary payloads are deliberately *not* stored in the IR: a book with three
    hundred scanned pages would make the tree unusable in memory and unreadable
    as JSON. The resource records where the bytes live and what they hash to,
    and the export pipeline streams them.

    Attributes:
        key: Identifier nodes refer to.
        kind: What the resource is.
        path: Where the bytes are, relative to the document or absolute.
        media_type: IANA media type.
        content_hash: Hash of the bytes, so a moved file is still recognisable
            and the same asset is embedded only once.
        byte_size: Size in bytes, for budgeting an export.
        width: Intrinsic width in pixels, for images.
        height: Intrinsic height in pixels, for images.
        dpi: Intrinsic resolution, for images.
        embed: Whether the asset should be embedded rather than linked.
        subset: Whether a font may be subsetted on embedding.
        family: Font family name, for font resources.
        weight: Font weight, for font resources.
        italic: Whether the font resource is the italic face.
        license_note: Licensing note, which matters for embedded fonts.
        description: Free-form remark.
    """

    key: str
    kind: ResourceKind = ResourceKind.IMAGE
    path: str | None = None
    media_type: str | None = None
    content_hash: str | None = None
    byte_size: int | None = None
    width: int | None = None
    height: int | None = None
    dpi: float | None = None
    embed: bool = True
    subset: bool = True
    family: str | None = None
    weight: int | None = None
    italic: bool = False
    license_note: str | None = None
    description: str | None = None


@ir_node("document_metadata")
@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentMetadata:
    """Bibliographic description of the document.

    Attributes:
        title: Main title.
        subtitle: Subtitle.
        short_title: Running-head form of the title.
        contributors: Everyone credited, in printing order.
        language: BCP-47 tag of the document's main language.
        additional_languages: Other languages present, which matter for
            hyphenation and for screen readers.
        identifier: Primary identifier, e.g. a UUID or a DOI. EPUB requires
            one.
        isbn: ISBN-13.
        issn: ISSN, for serials.
        publisher: Publisher name.
        imprint: Imprint, when it differs from the publisher.
        publication_date: Date of publication.
        modified: Last modification timestamp, required by EPUB 3.
        edition: Edition statement, e.g. ``"2a edicao revista"``.
        series: Series title.
        series_index: Position within the series.
        description: Blurb or abstract.
        subjects: Subject headings and keywords.
        rights: Copyright statement.
        source: Where this document was derived from -- the scanned book, the
            original PDF.
        cover_resource: Key of the resource used as the cover.
        page_count: Page count of the source, when known.
        custom: Everything else, in source order.
    """

    title: str = ""
    subtitle: str | None = None
    short_title: str | None = None
    contributors: tuple[Contributor, ...] = ()
    language: str = "pt-BR"
    additional_languages: tuple[str, ...] = ()
    identifier: str | None = None
    isbn: str | None = None
    issn: str | None = None
    publisher: str | None = None
    imprint: str | None = None
    publication_date: str | None = None
    modified: datetime | None = None
    edition: str | None = None
    series: str | None = None
    series_index: int | None = None
    description: str | None = None
    subjects: tuple[str, ...] = ()
    rights: str | None = None
    source: str | None = None
    cover_resource: str | None = None
    page_count: int | None = None
    custom: tuple[MetadataEntry, ...] = ()

    @property
    def authors(self) -> tuple[Contributor, ...]:
        """The contributors credited as authors."""
        return tuple(c for c in self.contributors if c.role is ContributorRole.AUTHOR)


@ir_node("document_settings")
@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentSettings:
    """Document-wide behaviour every exporter honours.

    These are the switches that make a book consistent: change
    ``notation_language`` and every move in every game, diagram caption and
    running paragraph reprints in the new language, because the moves were never
    text.

    Attributes:
        notation_language: BCP-47 tag moves are printed in.
        move_render: Figurine, language letters, or both.
        figurine_set: Which glyph set figurine forms use.
        chess_font_family: Font used for board glyphs and figurine, overriding
            each diagram style's own.
        default_diagram_style: Diagram style applied where none is named.
        diagram_numbering_start: First automatic diagram number.
        figure_numbering_start: First automatic figure number.
        table_numbering_start: First automatic table number.
        auto_number_diagrams: Whether diagrams are numbered automatically.
        number_diagrams_per_chapter: Restart diagram numbering at each level-1
            heading.
        hyphenation: Whether text may be hyphenated.
        footnote_restart_per_page: Restart footnote numbering on each page.
        confidence_threshold: Confidence below which a recognised square is
            shown as doubtful.
        embed_fonts: Whether fonts are embedded on export.
    """

    notation_language: str = DEFAULT_LANGUAGE
    move_render: MoveRenderStyle = MoveRenderStyle.LETTERS
    figurine_set: FigurineSet = FigurineSet.BLACK
    chess_font_family: str | None = None
    default_diagram_style: str | None = None
    diagram_numbering_start: int = 1
    figure_numbering_start: int = 1
    table_numbering_start: int = 1
    auto_number_diagrams: bool = True
    number_diagrams_per_chapter: bool = False
    hyphenation: bool = True
    footnote_restart_per_page: bool = False
    confidence_threshold: float = 0.9
    embed_fonts: bool = True


@ir_node("document")
@dataclass(frozen=True, slots=True, kw_only=True)
class Document(IRNode):
    """The root of the Document IR.

    Attributes:
        metadata: Bibliographic description.
        styles: Named, inheritable styles and document defaults.
        settings: Document-wide behaviour.
        resources: Embedded and referenced assets.
        body: The block tree.
    """

    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    styles: StyleSheet = field(default_factory=StyleSheet)
    settings: DocumentSettings = field(default_factory=DocumentSettings)
    resources: tuple[Resource, ...] = ()
    body: tuple[Block, ...] = ()

    def resource(self, key: str) -> Resource | None:
        """Look up a resource by key.

        Args:
            key: The resource key a node refers to.

        Returns:
            The resource, or ``None`` when it is not declared.
        """
        return next((item for item in self.resources if item.key == key), None)
