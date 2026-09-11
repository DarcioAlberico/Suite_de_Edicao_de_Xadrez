"""EPUB 3 output: reflowable by default, fixed-layout on request.

# Origem: PDFimport/PDFImport_v1.2.0/PDFImport/builder.py (614 linhas)
# Absorvido em 2026-09-07. Alteracoes e por que:
#   - o gerador de secoes, o NCX, o NAV e o OPF foram reescritos sobre o
#     Document IR em vez do modelo de blocos daquele projeto, porque a fonte
#     agora e uma arvore semantica e nao uma lista de paragrafos vindos do PDF;
#   - `_font_plan` foi mantido quase intacto: a ideia de declarar cada face sob
#     o nome da familia com `unicode-range`, para que dois subconjuntos da mesma
#     face sirvam cada um os caracteres que carrega, e exatamente o que um livro
#     digitalizado com fontes por capitulo exige, e nao havia como melhorar;
#   - `build_epub` manteve a disciplina que faz o arquivo ser aceito: o
#     `mimetype` primeiro e sem compressao. Errar isso e ter um EPUB que nenhum
#     leitor abre, e e o tipo de erro que so aparece no dispositivo do usuario.

SPEC section 8.3 asks for semantic XHTML, modular CSS, inline SVG diagrams,
embedded and subset chess fonts, ``nav.xhtml`` with landmarks, Dublin Core
metadata, and a clean EPUBCheck. The markup engine is
:mod:`caissa.export.html`; what is here is the container, the package document
and the parts that make a reader accept the file.

Why the diagrams are inline SVG and not images
----------------------------------------------
An ``<img src="d1.svg">`` in an EPUB is a black box: it cannot inherit the
reader's colours, so a diagram drawn for white paper stays white in night mode
and blinds the reader, and it cannot be styled or measured by the page. Inline
``<svg>`` is part of the document -- it scales with the type, it takes the
reader's ``currentColor`` where we ask it to, and it stays sharp at any zoom
because it is geometry rather than pixels. It costs bytes; a chess book is worth
the bytes.

Fixed layout
------------
Some books cannot reflow: a page whose diagrams sit in the margin beside the
line they annotate is a *design*, not a stream of paragraphs. For those,
``EpubOptions(layout="fixed")`` writes ``rendition:layout pre-paginated`` with a
viewport per page, and the same content flows into pages of a declared size.
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal
from uuid import uuid4

from caissa.core.model import (
    Block,
    ContributorRole,
    Document,
    DocumentMetadata,
    Heading,
    ResourceKind,
    document_to_payload,
)
from caissa.export.base import ExportContext, Exporter, ExportError, ExportOptions, ExportResult
from caissa.export.html import (
    BASE_CSS,
    REPLAY_SCRIPT,
    XhtmlBuilder,
    _css_cdata,
    escape,
    escape_attr,
    fill_note_slots,
    split_markup,
)
from caissa.export.profiles import EPUB_PROFILE

__all__ = ["EpubExporter", "EpubOptions", "read_epub"]

_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})


CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

FIXED_LAYOUT_CSS = """\
/* Layout fixo: a pagina tem tamanho declarado e nada reflui. */
body { margin: 0; padding: 0; width: 100%; height: 100%; }
.page { position: relative; width: 100%; height: 100%; overflow: hidden;
        box-sizing: border-box; padding: 6% 8%; }
"""

CHESS_CSS = """\
/* Diagramas e notacao. Separado da folha base porque um livro sem xadrez
   nao precisa carregar nada disto, e porque e a folha que o usuario troca
   quando quer outro visual de tabuleiro. */
figure.diagram { margin: 1.4em 0; text-align: center; break-inside: avoid; }
figure.diagram svg { display: block; margin: 0 auto; max-width: 100%; height: auto; }
figure.diagram figcaption .label { font-weight: 600; }
figure.diagram figcaption .stipulation { font-style: italic; }
.diagram-inline { display: inline-block; vertical-align: -0.35em; }
.diagram-inline svg { height: 2.2em; width: auto; }
.move { white-space: nowrap; }
.movetext .variation { font-size: 0.94em; }
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class EpubOptions(ExportOptions):
    """Settings specific to EPUB output.

    Attributes:
        layout: ``"reflowable"`` or ``"fixed"``.
        page_width: Fixed-layout page width in CSS pixels.
        page_height: Fixed-layout page height in CSS pixels.
        split_level: Heading level that starts a new XHTML document. One file
            per chapter is what keeps a reader responsive on a four-hundred-page
            book; one giant file is what makes it stutter.
        include_ncx: Also write the EPUB 2 ``toc.ncx``. Not required by EPUB 3,
            but old readers still look for it and it costs a kilobyte.
        max_section_bytes: Split a chapter further when its XHTML exceeds this,
            at the next heading of any level.
    """

    layout: Literal["reflowable", "fixed"] = "reflowable"
    page_width: int = 768
    page_height: int = 1024
    split_level: int = 1
    include_ncx: bool = True
    max_section_bytes: int = 260_000


@dataclass(frozen=True, slots=True)
class _Section:
    """One XHTML document inside the package.

    Attributes:
        name: File name inside ``OEBPS/Text``.
        title: Navigation label.
        body: The rendered markup.
        anchors: Element ids the section contains, for cross-file links.
        headings: ``(level, anchor, title)`` triples the section contains.
    """

    name: str
    title: str
    body: str
    anchors: frozenset[str]
    headings: tuple[tuple[int, str, str], ...]


@dataclass(frozen=True, slots=True)
class _FontFace:
    """One embedded font face.

    Attributes:
        file_name: File name inside ``OEBPS/Fonts``.
        family: CSS family name.
        data: The subset bytes.
        media_type: IANA media type.
        weight: CSS weight.
        italic: Whether this is the italic face.
        coverage: Codepoints the subset carries, for ``unicode-range``.
    """

    file_name: str
    family: str
    data: bytes
    media_type: str
    weight: int = 400
    italic: bool = False
    coverage: frozenset[int] = frozenset()


class EpubExporter(Exporter):
    """Writes an EPUB 3 package."""

    format_name: ClassVar[str] = "epub"
    profile: ClassVar[Any] = EPUB_PROFILE
    suffix: ClassVar[str] = ".epub"

    def write(
        self, document: Document, destination: Path, context: ExportContext
    ) -> ExportResult:
        """Write the package.

        Args:
            document: The IR to write.
            destination: The ``.epub`` file.
            context: The export context.

        Returns:
            The result.

        Raises:
            ExportError: The package could not be written.
        """
        options = context.options
        fixed = getattr(options, "layout", "reflowable") == "fixed"
        if fixed:
            context.audit_feature("fixed_layout", original="pre-paginated")

        builder = XhtmlBuilder(context, epub=True, interactive=options.interactive)
        sections = self._sections(document, context, builder, fixed=fixed)
        if not sections:
            raise ExportError("O documento nao tem conteudo para exportar em EPUB.")

        hrefs = {
            anchor: f"{section.name}#{anchor}"
            for section in sections
            for anchor in section.anchors
        }
        nav_entries = [
            (level, f"Text/{section.name}#{anchor}", title)
            for section in sections
            for level, anchor, title in section.headings
        ]
        if not nav_entries:
            nav_entries = [(1, f"Text/{sections[0].name}", sections[0].title)]

        fonts = self._font_plan(document, builder, context)
        identifier = document.metadata.identifier or f"urn:uuid:{uuid4()}"
        modified = document.metadata.modified or datetime.now(UTC)

        known = frozenset(hrefs)
        sections = [
            _Section(
                name=section.name,
                title=section.title,
                body=_resolve_links(section.body, section.name, hrefs, known, context),
                anchors=section.anchors,
                headings=section.headings,
            )
            for section in sections
        ]

        files: list[tuple[str, bytes, int]] = []
        for section in sections:
            page = self._page(document, context, section, fixed=fixed, fonts=bool(fonts))
            files.append((f"OEBPS/Text/{section.name}", page.encode("utf-8"), zipfile.ZIP_DEFLATED))

        stylesheets = {
            "base.css": BASE_CSS,
            "chess.css": CHESS_CSS,
            "props.css": _without_direction(builder.stylesheet()),
        }
        if fixed:
            stylesheets["fixed.css"] = FIXED_LAYOUT_CSS
        if fonts:
            stylesheets["fonts.css"] = _font_face_css(fonts)
        for name, text in stylesheets.items():
            files.append((f"OEBPS/Styles/{name}", text.encode("utf-8"), zipfile.ZIP_DEFLATED))

        for face in fonts:
            files.append((f"OEBPS/Fonts/{face.file_name}", face.data, zipfile.ZIP_STORED))

        nav = _nav_xhtml(document, nav_entries, sections, language=_language(document, context))
        files.append(("OEBPS/nav.xhtml", nav.encode("utf-8"), zipfile.ZIP_DEFLATED))

        if getattr(options, "include_ncx", True):
            ncx = _ncx(document, nav_entries, identifier, _language(document, context))
            files.append(("OEBPS/toc.ncx", ncx.encode("utf-8"), zipfile.ZIP_DEFLATED))

        if options.embed_ir:
            import json

            payload = json.dumps(
                document_to_payload(document), ensure_ascii=False, separators=(",", ":")
            )
            files.append(
                ("OEBPS/caissa-ir.json", payload.encode("utf-8"), zipfile.ZIP_DEFLATED)
            )

        opf = _opf(
            document,
            context,
            sections=sections,
            stylesheets=tuple(stylesheets),
            fonts=fonts,
            identifier=identifier,
            modified=modified,
            fixed=fixed,
            include_ncx=getattr(options, "include_ncx", True),
            include_ir=options.embed_ir,
            interactive=options.interactive,
        )
        files.append(("OEBPS/content.opf", opf.encode("utf-8"), zipfile.ZIP_DEFLATED))
        files.append(
            ("META-INF/container.xml", CONTAINER_XML.encode("utf-8"), zipfile.ZIP_DEFLATED)
        )
        if options.interactive:
            files.append(
                ("OEBPS/Scripts/replay.js", REPLAY_SCRIPT.encode("utf-8"), zipfile.ZIP_DEFLATED)
            )

        self._zip(destination, files)
        context.count("sections", len(sections))
        context.count("fonts", len(fonts))
        context.count("bytes", destination.stat().st_size)
        if fonts:
            context.note(
                "Fontes embutidas e subconjuntadas: "
                + ", ".join(f"{face.file_name} ({len(face.data)} bytes)" for face in fonts)
            )
        return context.finish(destination)

    # -- pieces ------------------------------------------------------------

    def _sections(
        self,
        document: Document,
        context: ExportContext,
        builder: XhtmlBuilder,
        *,
        fixed: bool,
    ) -> list[_Section]:
        """Render the body and split it into XHTML documents.

        Args:
            document: The IR.
            context: The export context.
            builder: The markup builder.
            fixed: Whether the package is fixed-layout.

        Returns:
            The sections, in spine order.
        """
        level = getattr(context.options, "split_level", 1)
        limit = getattr(context.options, "max_section_bytes", 260_000)

        groups: list[list[Block]] = [[]]
        for block in document.body:
            if isinstance(block, Heading) and block.level <= level and groups[-1]:
                groups.append([])
            groups[-1].append(block)
        groups = [group for group in groups if group] or [list(document.body)]

        sections: list[_Section] = []
        for index, group in enumerate(groups):
            start = len(builder.headings)
            body = builder.blocks(tuple(group))
            headings = tuple(builder.headings[start:])
            title = headings[0][2] if headings else (document.metadata.title or "Texto")
            for part_index, chunk in enumerate(_split_by_size(body, limit)):
                name = f"s{index:03d}{'' if part_index == 0 else f'-{part_index}'}.xhtml"
                anchors = frozenset(re.findall(r'\sid="([^"]+)"', chunk))
                sections.append(
                    _Section(
                        name=name,
                        title=title if part_index == 0 else f"{title} ({part_index + 1})",
                        body=chunk,
                        anchors=anchors,
                        headings=tuple(
                            triple for triple in headings if triple[1] in anchors
                        ),
                    )
                )

        notes = builder.notes_section()
        if notes:
            anchors = frozenset(re.findall(r'\sid="([^"]+)"', notes))
            sections.append(
                _Section(
                    name="notas.xhtml",
                    title="Notas",
                    body=notes,
                    anchors=anchors,
                    headings=((1, "notas", "Notas"),) if "notas" in anchors else (),
                )
            )
        index_html = builder.index_html()
        if index_html:
            sections.append(
                _Section(
                    name="remissivo.xhtml",
                    title="Indice remissivo",
                    body=index_html,
                    anchors=frozenset(),
                    headings=(),
                )
            )
        return sections

    def _page(
        self,
        document: Document,
        context: ExportContext,
        section: _Section,
        *,
        fixed: bool,
        fonts: bool,
    ) -> str:
        """Wrap a section body in a complete XHTML document.

        Args:
            document: The IR.
            context: The export context.
            section: The section.
            fixed: Whether the package is fixed-layout.
            fonts: Whether a font stylesheet exists.

        Returns:
            The XHTML.
        """
        language = _language(document, context)
        links = ['<link rel="stylesheet" type="text/css" href="../Styles/base.css"/>',
                 '<link rel="stylesheet" type="text/css" href="../Styles/chess.css"/>',
                 '<link rel="stylesheet" type="text/css" href="../Styles/props.css"/>']
        if fonts:
            links.append('<link rel="stylesheet" type="text/css" href="../Styles/fonts.css"/>')
        if fixed:
            links.append('<link rel="stylesheet" type="text/css" href="../Styles/fixed.css"/>')
        viewport = ""
        if fixed:
            width = getattr(context.options, "page_width", 768)
            height = getattr(context.options, "page_height", 1024)
            viewport = f'<meta name="viewport" content="width={width}, height={height}"/>'
        script = ""
        if context.options.interactive:
            script = '<script src="../Scripts/replay.js"><![CDATA[]]></script>'
        body_class = ' class="page"' if fixed else ""
        return (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" '
            f'xml:lang="{escape_attr(language)}" lang="{escape_attr(language)}">\n'
            "<head>\n"
            f"<title>{escape(section.title)}</title>\n"
            f"{viewport}\n"
            + "\n".join(links)
            + "\n</head>\n"
            f"<body{body_class}>\n"
            f'<section epub:type="chapter">\n{section.body}\n</section>\n'
            f"{script}\n"
            "</body>\n</html>\n"
        )

    def _font_plan(
        self, document: Document, builder: XhtmlBuilder, context: ExportContext
    ) -> tuple[_FontFace, ...]:
        """Subset and collect every font the package should carry.

        Two sources feed this. Fonts the document declares as resources -- the
        faces an importer lifted out of the source PDF -- are subset to the
        characters the text actually sets. Chess families the diagrams named are
        subset to their piece glyphs. Both go through ``fontTools`` with a
        rebuilt Unicode ``cmap``, because a legacy chess font that answers only
        to ``U+F070`` is invisible in a reader that asks for ``U+0070``.

        Args:
            document: The IR.
            builder: The markup builder, for the chess families it used.
            context: The export context.

        Returns:
            The faces to embed.
        """
        if not context.options.embed_fonts or not document.settings.embed_fonts:
            return ()

        faces: list[_FontFace] = []
        used = _characters_by_family(document)

        for resource in document.resources:
            if resource.kind is not ResourceKind.FONT or not resource.embed:
                continue
            path = Path(resource.path) if resource.path else None
            if path is None or not path.exists():
                context.recorder.substituted(
                    prop="font_embedding",
                    path=context.path,
                    original=resource.family or resource.key,
                    replacement="referencia por nome",
                    detail=(
                        f"O arquivo da fonte '{resource.key}' nao foi encontrado; o EPUB "
                        "referencia a familia pelo nome e o leitor usara um substituto."
                    ),
                )
                continue
            family = resource.family or path.stem
            characters = used.get(family) or used.get(family.lower()) or set()
            try:
                data, coverage = _subset_resource(path, characters, resource.subset)
            except Exception as error:
                context.recorder.substituted(
                    prop="font_embedding",
                    path=context.path,
                    original=family,
                    replacement="referencia por nome",
                    detail=f"A fonte nao pode ser subconjuntada: {error}",
                )
                continue
            faces.append(
                _FontFace(
                    file_name=_safe_name(family, path.suffix or ".ttf"),
                    family=family,
                    data=data,
                    media_type=_font_media_type(path.suffix),
                    weight=resource.weight or 400,
                    italic=resource.italic,
                    coverage=frozenset(coverage),
                )
            )

        drawn = builder.diagrams.used_characters()
        for family, wanted in _chess_families(builder.diagrams.font_families, drawn, used):
            if not wanted:
                continue
            try:
                from caissa.typeset.fonts import get_spec, subset_font, woff2_available

                # WOFF2 is smaller and every EPUB 3 reader takes it, but writing
                # it needs Brotli. TrueType is an EPUB 3 core media type too, so
                # a machine without the compressor still ships the face rather
                # than silently shipping none.
                compressed = woff2_available()
                flavour = "woff2" if compressed else None
                data = subset_font(family, wanted, flavor=flavour)
                spec = get_spec(family)
            except Exception as error:
                context.recorder.substituted(
                    prop="font_embedding",
                    path=context.path,
                    original=family,
                    replacement="referencia por nome de familia",
                    detail=(
                        f"A fonte de xadrez '{family}' nao pode ser subconjuntada "
                        f"({error}); o EPUB referencia a familia pelo nome e o leitor "
                        "usara um substituto."
                    ),
                )
                continue
            suffix = ".woff2" if compressed else ".ttf"
            faces.append(
                _FontFace(
                    file_name=_safe_name(spec.family, suffix),
                    family=spec.family,
                    data=data,
                    media_type="font/woff2" if compressed else "font/ttf",
                    coverage=frozenset(ord(char) for char in wanted),
                )
            )
        return tuple(faces)



    @staticmethod
    def _zip(destination: Path, files: Sequence[tuple[str, bytes, int]]) -> None:
        """Write the package, mimetype first and stored.

        This is the one detail that decides whether a reader opens the file at
        all: the OCF specification requires the ``mimetype`` entry to be the
        first in the archive and to be stored uncompressed, with no extra field.
        Deflate it and half the readers on the market reject the book.

        Args:
            destination: The ``.epub`` path.
            files: ``(name, data, compress_type)`` triples.
        """
        ordered = {name: (data, method) for name, data, method in files}
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo("mimetype")
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, b"application/epub+zip")
            for name in ("META-INF/container.xml", "OEBPS/content.opf"):
                if name in ordered:
                    data, method = ordered.pop(name)
                    archive.writestr(zipfile.ZipInfo(name), data, compress_type=method)
            for name, (data, method) in ordered.items():
                archive.writestr(zipfile.ZipInfo(name), data, compress_type=method)


# --------------------------------------------------------------------------- #
# Package document
# --------------------------------------------------------------------------- #
_ROLE_MARC: Mapping[ContributorRole, str] = {
    ContributorRole.AUTHOR: "aut",
    ContributorRole.EDITOR: "edt",
    ContributorRole.TRANSLATOR: "trl",
    ContributorRole.ILLUSTRATOR: "ill",
    ContributorRole.ANNOTATOR: "ann",
    ContributorRole.COMPILER: "com",
    ContributorRole.FOREWORD: "aui",
    ContributorRole.PUBLISHER: "pbl",
    ContributorRole.CONTRIBUTOR: "ctb",
    ContributorRole.DESIGNER: "bkd",
    ContributorRole.PHOTOGRAPHER: "pht",
}


def _without_direction(css: str) -> str:
    """Strip the one declaration EPUB refuses to allow in a stylesheet.

    EPUB 3.2 requires writing direction to come from the ``dir`` attribute, and
    EPUBCheck reports every ``direction`` declaration as an error. The value is
    not lost: :func:`caissa.export.html.run_props_to_css` also writes it as
    ``--caissa-rdirection`` / ``--caissa-pdirection``, which is what the
    re-import reads.

    Args:
        css: The generated stylesheet.

    Returns:
        The stylesheet without ``direction`` declarations.
    """
    return re.sub(r"(?<![-\w])direction:\s*[^;}]*;\s*", "", css)


def _language(document: Document, context: ExportContext) -> str:
    """Choose the package language.

    Args:
        document: The IR.
        context: The export context.

    Returns:
        A BCP-47 tag.
    """
    return context.options.language or document.metadata.language or "pt-BR"


def _opf(
    document: Document,
    context: ExportContext,
    *,
    sections: Sequence[_Section],
    stylesheets: Sequence[str],
    fonts: Sequence[_FontFace],
    identifier: str,
    modified: datetime,
    fixed: bool,
    include_ncx: bool,
    include_ir: bool,
    interactive: bool,
) -> str:
    """Build the package document.

    Args:
        document: The IR.
        context: The export context.
        sections: The XHTML documents, in spine order.
        stylesheets: Stylesheet file names.
        fonts: Embedded faces.
        identifier: The unique identifier.
        modified: The ``dcterms:modified`` timestamp EPUB 3 requires.
        fixed: Whether the package is fixed-layout.
        include_ncx: Whether ``toc.ncx`` is present.
        include_ir: Whether the IR sidecar is present.
        interactive: Whether the replay script is present.

    Returns:
        The OPF XML.
    """
    metadata = document.metadata
    language = _language(document, context)
    stamp = modified.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    meta: list[str] = [
        f'<dc:identifier id="pub-id">{escape(identifier)}</dc:identifier>',
        # The document's own node id, so a re-import finds the tree's root
        # again. It is a Dublin Core "source" refinement, not an invention.
        f'<meta property="caissa:document-id">{escape(str(document.id))}</meta>',
        # EPUB demands a unique identifier; when the document had none we mint
        # one, and this says so, so a re-import does not hand the user a UUID
        # they never chose.
        f'<meta property="caissa:minted-identifier">'
        f'{"1" if not metadata.identifier else "0"}</meta>',
        f"<dc:title>{escape(metadata.title or 'Documento')}</dc:title>",
        f"<dc:language>{escape(language)}</dc:language>",
        f'<meta property="dcterms:modified">{stamp}</meta>',
    ]
    if metadata.subtitle:
        meta.append(f'<dc:title id="subtitle">{escape(metadata.subtitle)}</dc:title>')
        meta.append('<meta refines="#subtitle" property="title-type">subtitle</meta>')
    for index, contributor in enumerate(metadata.contributors):
        tag = "dc:creator" if contributor.role is ContributorRole.AUTHOR else "dc:contributor"
        ident = f"c{index}"
        meta.append(f'<{tag} id="{ident}">{escape(contributor.name)}</{tag}>')
        meta.append(
            f'<meta refines="#{ident}" property="role" scheme="marc:relators">'
            f"{_ROLE_MARC.get(contributor.role, 'ctb')}</meta>"
        )
        if contributor.sort_name:
            meta.append(
                f'<meta refines="#{ident}" property="file-as">'
                f"{escape(contributor.sort_name)}</meta>"
            )
    if metadata.publisher:
        meta.append(f"<dc:publisher>{escape(metadata.publisher)}</dc:publisher>")
    if metadata.description:
        meta.append(f"<dc:description>{escape(metadata.description)}</dc:description>")
    if metadata.publication_date:
        meta.append(f"<dc:date>{escape(metadata.publication_date)}</dc:date>")
    if metadata.rights:
        meta.append(f"<dc:rights>{escape(metadata.rights)}</dc:rights>")
    if metadata.source:
        meta.append(f"<dc:source>{escape(metadata.source)}</dc:source>")
    for subject in metadata.subjects:
        meta.append(f"<dc:subject>{escape(subject)}</dc:subject>")
    if metadata.isbn:
        meta.append(
            f'<dc:identifier id="isbn">urn:isbn:{escape(metadata.isbn)}</dc:identifier>'
        )
    for entry in metadata.custom:
        meta.append(
            f'<meta property="{escape_attr(entry.scheme or "caissa")}:'
            f'{escape_attr(entry.name)}">{escape(entry.value)}</meta>'
        )
    meta.append(
        '<meta property="rendition:layout">'
        + ("pre-paginated" if fixed else "reflowable")
        + "</meta>"
    )
    meta.append('<meta property="schema:accessMode">textual</meta>')
    meta.append('<meta property="schema:accessMode">visual</meta>')
    meta.append('<meta property="schema:accessibilityFeature">structuralNavigation</meta>')
    meta.append('<meta property="schema:accessibilityFeature">alternativeText</meta>')
    meta.append(
        '<meta property="schema:accessibilitySummary">'
        "Diagramas de xadrez em SVG com descricao textual da posicao."
        "</meta>"
    )

    manifest: list[str] = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
    ]
    if include_ncx:
        manifest.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
    spine: list[str] = []
    for index, section in enumerate(sections):
        ident = f"s{index:03d}"
        properties = _section_properties(section, interactive=interactive)
        attribute = f' properties="{" ".join(properties)}"' if properties else ""
        manifest.append(
            f'<item id="{ident}" href="Text/{escape_attr(section.name)}" '
            f'media-type="application/xhtml+xml"{attribute}/>'
        )
        spine.append(f'<itemref idref="{ident}"/>')
    spine.append('<itemref idref="nav" linear="no"/>')
    for name in stylesheets:
        ident = f"css-{re.sub(r'[^a-z0-9]', '-', name.lower())}"
        manifest.append(
            f'<item id="{ident}" href="Styles/{escape_attr(name)}" media-type="text/css"/>'
        )
    for index, face in enumerate(fonts):
        manifest.append(
            f'<item id="font{index}" href="Fonts/{escape_attr(face.file_name)}" '
            f'media-type="{face.media_type}"/>'
        )
    if interactive:
        manifest.append(
            '<item id="replay" href="Scripts/replay.js" media-type="text/javascript"/>'
        )
    if include_ir:
        manifest.append(
            '<item id="caissa-ir" href="caissa-ir.json" media-type="application/json"/>'
        )
    if metadata.cover_resource:
        resource = document.resource(metadata.cover_resource)
        # A manifest item for a file the package does not carry is what makes a
        # reader refuse the book, so the cover is declared only when it is here.
        if resource is not None and resource.path and Path(resource.path).exists():
            manifest.append(
                f'<item id="cover-image" href="{escape_attr(resource.path)}" '
                f'media-type="{escape_attr(resource.media_type or "image/jpeg")}" '
                'properties="cover-image"/>'
            )

    toc_attr = ' toc="ncx"' if include_ncx else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="pub-id" '
        'prefix="schema: http://schema.org/ '
        'rendition: http://www.idpf.org/vocab/rendition/# '
        'caissa: https://caissa.studio/ns#">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:opf="http://www.idpf.org/2007/opf">\n'
        + "\n".join(meta)
        + "\n</metadata>\n<manifest>\n"
        + "\n".join(manifest)
        + f"\n</manifest>\n<spine{toc_attr}>\n"
        + "\n".join(spine)
        + "\n</spine>\n</package>\n"
    )


def _resolve_links(
    body: str,
    name: str,
    hrefs: Mapping[str, str],
    known: frozenset[str],
    context: ExportContext,
) -> str:
    """Point every internal link at the file that actually holds its target.

    One XHTML document per chapter is what keeps a reader responsive, and it is
    also what turns every ``href="#anchor"`` into a cross-file reference the
    moment the target lands in another chapter. A link that still says ``#x``
    when ``x`` is three files away is a link that does nothing, and EPUBCheck
    says so.

    A fragment that exists nowhere in the package loses its ``href`` entirely:
    an anchor without one is valid XHTML and inert, which is honest, where a
    dangling href is neither.

    Args:
        body: The rendered section.
        name: The section's file name.
        hrefs: Every anchor in the package, mapped to ``file#anchor``.
        known: The anchor names, for the membership test.
        context: The export context, for the degradation report.

    Returns:
        The section with its links resolved.
    """
    dangling: list[str] = []

    def replace(match: re.Match[str]) -> str:
        target = match.group(1)
        if target not in known:
            dangling.append(target)
            return f'data-unresolved="{escape_attr(target)}"'
        full = hrefs[target]
        if full.startswith(f"{name}#"):
            return f'href="#{escape_attr(target)}"'
        return f'href="{escape_attr(full)}"'

    resolved = re.sub(r'href="#([^"]+)"', replace, body)
    for target in dangling:
        context.recorder.unsupported(
            prop="link_target",
            path=name,
            original=f"#{target}",
            detail=(
                f"O documento tem uma ligacao para '#{target}', que nao existe em "
                "lugar nenhum do livro. A ancora foi mantida sem destino, porque um "
                "destino quebrado faz o leitor recusar o arquivo."
            ),
        )
    return resolved


def _section_properties(section: _Section, *, interactive: bool) -> list[str]:
    """Work out the manifest properties one section actually needs.

    EPUBCheck rejects a declared property the section does not use just as
    firmly as an undeclared one it does, so both directions are computed from
    the markup rather than assumed.

    Args:
        section: The section.
        interactive: Whether the package carries the replay script.

    Returns:
        The property names, in a stable order.
    """
    properties: list[str] = []
    if "<svg" in section.body:
        properties.append("svg")
    if "<math" in section.body:
        properties.append("mathml")
    if interactive and 'data-pgn' in section.body:
        properties.append("scripted")
    return properties


def _nav_xhtml(
    document: Document,
    entries: Sequence[tuple[int, str, str]],
    sections: Sequence[_Section],
    *,
    language: str,
) -> str:
    """Build ``nav.xhtml`` with a table of contents and landmarks.

    Landmarks are what let a reader jump to "start of the text" rather than to
    page one of the front matter, and EPUB accessibility checks look for them.

    Args:
        document: The IR.
        entries: ``(level, href, title)`` triples in document order.
        sections: The XHTML documents, for the landmark targets.
        language: The package language.

    Returns:
        The XHTML.
    """
    toc = _nav_list(entries)
    landmarks = [
        '<li><a epub:type="toc" href="nav.xhtml">Sum&#225;rio</a></li>',
        f'<li><a epub:type="bodymatter" href="Text/{escape_attr(sections[0].name)}">'
        "In&#237;cio do texto</a></li>",
    ]
    for section in sections:
        if section.name == "notas.xhtml":
            landmarks.append(
                '<li><a epub:type="footnotes" href="Text/notas.xhtml">Notas</a></li>'
            )
        if section.name == "remissivo.xhtml":
            landmarks.append(
                '<li><a epub:type="index" href="Text/remissivo.xhtml">'
                "&#205;ndice remissivo</a></li>"
            )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" '
        f'xml:lang="{escape_attr(language)}" lang="{escape_attr(language)}">\n'
        "<head>\n<title>Sum&#225;rio</title>\n"
        '<link rel="stylesheet" type="text/css" href="Styles/base.css"/>\n'
        "</head>\n<body>\n"
        f'<nav epub:type="toc" id="toc" role="doc-toc">\n<h1>Sum&#225;rio</h1>\n{toc}\n</nav>\n'
        f'<nav epub:type="landmarks" id="landmarks" hidden="hidden">\n'
        f"<h2>Marcos</h2>\n<ol>\n" + "\n".join(landmarks) + "\n</ol>\n</nav>\n"
        "</body>\n</html>\n"
    )


def _nav_list(entries: Sequence[tuple[int, str, str]]) -> str:
    """Build a nested ``<ol>`` for the navigation document.

    Args:
        entries: ``(level, href, title)`` triples in document order.

    Returns:
        The list markup; EPUB requires a non-empty ``<ol>``.
    """
    if not entries:
        return "<ol><li><a href=\"nav.xhtml\">Sum&#225;rio</a></li></ol>"
    out: list[str] = []
    stack: list[int] = []
    for level, href, title in entries:
        while stack and stack[-1] > level:
            out.append("</li></ol>")
            stack.pop()
        if stack and stack[-1] == level:
            out.append("</li>")
        else:
            out.append("<ol>")
            stack.append(level)
        out.append(f'<li><a href="{escape_attr(href)}">{escape(title or "Sem titulo")}</a>')
    while stack:
        out.append("</li></ol>")
        stack.pop()
    return "".join(out)


def _ncx(
    document: Document,
    entries: Sequence[tuple[int, str, str]],
    identifier: str,
    language: str,
) -> str:
    """Build the EPUB 2 navigation control file.

    Args:
        document: The IR.
        entries: ``(level, href, title)`` triples in document order.
        identifier: The package identifier.
        language: The package language.

    Returns:
        The NCX XML.
    """
    points: list[str] = []
    for index, (_level, href, title) in enumerate(entries, start=1):
        points.append(
            f'<navPoint id="np{index}" playOrder="{index}">'
            f"<navLabel><text>{escape(title or 'Sem titulo')}</text></navLabel>"
            f'<content src="{escape_attr(href)}"/></navPoint>'
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" '
        f'xml:lang="{escape_attr(language)}">\n'
        "<head>\n"
        f'<meta name="dtb:uid" content="{escape_attr(identifier)}"/>\n'
        '<meta name="dtb:depth" content="2"/>\n'
        '<meta name="dtb:totalPageCount" content="0"/>\n'
        '<meta name="dtb:maxPageNumber" content="0"/>\n'
        "</head>\n"
        f"<docTitle><text>{escape(document.metadata.title or 'Documento')}</text></docTitle>\n"
        "<navMap>\n" + "\n".join(points) + "\n</navMap>\n</ncx>\n"
    )


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #
def _chess_families(
    drawn_families: Sequence[str],
    drawn: Mapping[str, set[str]],
    used: Mapping[str, set[str]],
) -> list[tuple[str, list[str]]]:
    """Decide which chess faces the package must carry, and what to keep of each.

    Two things can ask for a chess face, and until this front only one of them
    was heard. A **diagram** asks when it is set with a font rather than drawn
    as outlines. **Running text** asks whenever a run or a piece glyph names a
    chess family -- ``1.Nf3`` set in Chess Merida is a knight followed by a
    square, and a reader without the face sees the letter N.

    Args:
        drawn_families: Chess families the diagram renderer actually used.
        drawn: Characters each of those families must draw.
        used: Characters each family is asked to set anywhere in the text.

    Returns:
        One ``(family, characters)`` pair per face to embed, the characters
        sorted so the subset is reproducible.
    """
    from caissa.export.html import chess_font_spec

    wanted: dict[str, set[str]] = {}
    for family in drawn_families:
        wanted.setdefault(family, set()).update(drawn.get(family, set()))
        wanted[family].update(used.get(family, set()))
    for family, characters in used.items():
        spec = chess_font_spec(family)
        if spec is None or not characters:
            continue
        wanted.setdefault(spec.key, set()).update(characters)
    return [(family, sorted(chars)) for family, chars in sorted(wanted.items())]


def _characters_by_family(document: Document) -> dict[str, set[str]]:
    """Collect which characters each font family is asked to set.

    A subset that keeps too little is a book with missing glyphs; a subset that
    keeps everything is not a subset. Walking the tree for the answer is the
    only way to be exactly right.

    Args:
        document: The IR.

    Returns:
        A mapping from family name to the characters used in it.
    """
    from caissa.core.model import PieceGlyph, Text, walk
    from caissa.export.html import _glyph_for

    used: dict[str, set[str]] = {}
    default = document.styles.default_run.font_family
    for _path, node in walk(document):
        if isinstance(node, PieceGlyph):
            # A piece glyph names its own face, and the character it is written
            # as is the one that face has to carry.
            family = node.font_family or node.props.font_family or default
            if family:
                used.setdefault(family, set()).add(_glyph_for(node))
            continue
        if not isinstance(node, Text):
            continue
        family = node.props.font_family or default
        if not family:
            continue
        used.setdefault(family, set()).update(node.content)
    return used


def _subset_resource(
    path: Path, characters: Iterable[str], allow_subset: bool
) -> tuple[bytes, set[int]]:
    """Subset a font resource to the characters a document uses.

    Args:
        path: The font file.
        characters: The characters to keep.
        allow_subset: Whether the licence permits subsetting; when ``False`` the
            whole file is embedded.

    Returns:
        The font bytes and the codepoints they cover.

    Raises:
        Exception: ``fontTools`` refused the file.
    """
    from fontTools import subset as ft_subset
    from fontTools.ttLib import TTFont

    wanted = {ord(char) for char in characters if char and ord(char) > 31}
    if not allow_subset or not wanted:
        data = path.read_bytes()
        font = TTFont(str(path), fontNumber=0, lazy=True)
        coverage = set(font.getBestCmap())
        font.close()
        return data, coverage

    font = TTFont(str(path), fontNumber=0)
    options = ft_subset.Options()
    options.set(layout_features=["*"], name_IDs=["*"], name_legacy=True, notdef_outline=True)
    options.recalc_bounds = True
    subsetter = ft_subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(wanted))
    subsetter.subset(font)
    coverage = set(font.getBestCmap())
    try:
        font.flavor = "woff2"
    except Exception:
        font.flavor = None
    import io

    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue(), coverage


def unicode_range(codepoints: Iterable[int]) -> str:
    """Render a ``unicode-range`` value from a set of codepoints.

    # Origem: PDFimport/fontembed.py -- mesma ideia, reescrita para conjuntos
    # arbitrarios em vez da cobertura de uma face de PDF.

    Consecutive codepoints collapse into a range, which keeps the declaration
    short enough to be readable and is what makes two subsets of one family
    coexist: the reader picks the face that actually carries the character.

    Args:
        codepoints: The covered codepoints.

    Returns:
        The CSS value, empty when the set is empty.
    """
    ordered = sorted(set(codepoints))
    if not ordered:
        return ""
    parts: list[str] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        parts.append(_range_text(start, previous))
        start = previous = value
    parts.append(_range_text(start, previous))
    return ", ".join(parts)


def _range_text(start: int, end: int) -> str:
    """Render one ``unicode-range`` interval.

    Args:
        start: First codepoint.
        end: Last codepoint.

    Returns:
        ``U+xx`` or ``U+xx-yy``.
    """
    if start == end:
        return f"U+{start:04X}"
    return f"U+{start:04X}-{end:04X}"


def _font_face_css(fonts: Sequence[_FontFace]) -> str:
    """Build the ``@font-face`` stylesheet for the embedded faces.

    Args:
        fonts: The faces.

    Returns:
        The CSS.
    """
    lines = ["/* Fontes embutidas e subconjuntadas pela exportacao. */"]
    for face in fonts:
        coverage = unicode_range(face.coverage) or "U+0-10FFFF"
        lines.append(
            "@font-face {\n"
            f'  font-family: "{face.family}";\n'
            f"  font-weight: {face.weight};\n"
            f"  font-style: {'italic' if face.italic else 'normal'};\n"
            f'  src: url("../Fonts/{face.file_name}");\n'
            f"  unicode-range: {coverage};\n"
            "}"
        )
    return "\n".join(lines) + "\n"


def _safe_name(family: str, suffix: str) -> str:
    """Build a safe file name for an embedded font.

    Args:
        family: The family name.
        suffix: The file extension, dot included.

    Returns:
        The file name.
    """
    stem = re.sub(r"[^A-Za-z0-9_-]+", "", family) or "fonte"
    return f"{stem}{suffix}"


def _font_media_type(suffix: str) -> str:
    """Map a font file extension to its IANA media type.

    Args:
        suffix: The extension, dot included.

    Returns:
        The media type.
    """
    return {
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }.get(suffix.lower(), "font/ttf")


def _split_by_size(body: str, limit: int) -> list[str]:
    """Split rendered markup into chunks below a byte budget.

    Args:
        body: The rendered blocks.
        limit: Maximum bytes per chunk; zero disables splitting.

    Returns:
        One or more chunks, split at heading boundaries.
    """
    if limit <= 0 or len(body.encode("utf-8")) <= limit:
        return [body]
    pieces = split_markup(body, _HEADING_TAGS)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len((current + piece).encode("utf-8")) > limit:
            chunks.append(current)
            current = piece
        else:
            current += piece
    if current:
        chunks.append(current)
    return chunks or [body]


# --------------------------------------------------------------------------- #
# Reading back
# --------------------------------------------------------------------------- #
def read_epub(path: Path | str, *, use_sidecar: bool = False) -> Document:
    """Read an EPUB written by :class:`EpubExporter` back into the IR.

    The package is opened, the spine is followed in order, and each XHTML
    document is parsed by the same reader :func:`caissa.export.html.read_html`
    uses -- so what is measured is the markup and the stylesheet, not a private
    channel.

    Args:
        path: The ``.epub`` file.
        use_sidecar: Prefer the packaged IR JSON when present.

    Returns:
        The reconstructed document.

    Raises:
        ExportError: The package is unreadable.
    """
    import json
    import xml.etree.ElementTree as ET

    from caissa.core.model import document_from_payload

    with zipfile.ZipFile(Path(path)) as archive:
        names = set(archive.namelist())
        if use_sidecar and "OEBPS/caissa-ir.json" in names:
            document, _migrations = document_from_payload(
                json.loads(archive.read("OEBPS/caissa-ir.json"))
            )
            return document

        try:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
        except KeyError as error:
            raise ExportError("O EPUB nao tem META-INF/container.xml.") from error
        rootfile = container.find(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
        )
        opf_path = rootfile.get("full-path") if rootfile is not None else "OEBPS/content.opf"
        package = ET.fromstring(archive.read(opf_path))
        base = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""

        namespace = "{http://www.idpf.org/2007/opf}"
        manifest = {
            item.get("id"): item.get("href")
            for item in package.iter(f"{namespace}item")
        }
        spine = [
            manifest.get(ref.get("idref"))
            for ref in package.iter(f"{namespace}itemref")
        ]

        styles = ""
        for href in manifest.values():
            if href and href.endswith("props.css"):
                styles = archive.read(f"{base}/{href}" if base else href).decode("utf-8")

        # The sections are read into one list *before* the notes are put back,
        # because a note's body lives in notas.xhtml and the slot that says
        # where it stood lives in the section that referenced it. Filling the
        # slots per section would never find the pair.
        read: list[object] = []
        metadata: DocumentMetadata | None = None
        for href in spine:
            if not href:
                continue
            full = f"{base}/{href}" if base else href
            if full not in names:
                continue
            text = archive.read(full).decode("utf-8")
            page = _wrap_section(text, styles)
            read.extend(_section_blocks(page, styles))
        blocks: list[Block] = fill_note_slots(read)
        metadata = _metadata_from_opf(package)
        identity = _document_identity(package)

    rebuilt = Document(metadata=metadata or DocumentMetadata(), body=tuple(blocks))
    if identity is None:
        return rebuilt
    from dataclasses import replace

    return replace(rebuilt, id=identity)


def _section_blocks(page: str, styles: str) -> list[object]:
    """Read one spine document into blocks, keeping its note slots.

    Args:
        page: The section XHTML, already wrapped with the generated stylesheet.
        styles: The generated stylesheet text.

    Returns:
        The blocks and slots, in document order.
    """
    import xml.etree.ElementTree as ET

    from caissa.export.html import _Reader, _stylesheet_from_head, read_section_blocks

    body = re.sub(r"^<!DOCTYPE[^>]*>\s*", "", page.strip(), flags=re.I)
    root = ET.fromstring(body)
    return read_section_blocks(root, _Reader(_stylesheet_from_head(root.find("head"))))


def _document_identity(package: Any) -> Any:
    """Read the document's own node id out of the package metadata.

    Args:
        package: The parsed OPF root.

    Returns:
        The :class:`~caissa.core.model.ids.ULID`, or ``None`` when the package
        was written by something else.
    """
    from caissa.core.model import ULID

    for meta in package.iter("{http://www.idpf.org/2007/opf}meta"):
        if meta.get("property") == "caissa:document-id" and meta.text:
            try:
                return ULID.from_string(meta.text.strip())
            except (ValueError, TypeError):
                return None
    return None


def _wrap_section(xhtml: str, generated_css: str) -> str:
    """Inject the generated stylesheet into a section so the reader sees it.

    The EPUB keeps the document's formatting in ``Styles/props.css`` and links
    to it; the HTML reader expects it in an identified ``<style>``. Splicing it
    in here keeps one reader for both formats instead of two that can disagree.

    Args:
        xhtml: The section document.
        generated_css: The contents of ``props.css``.

    Returns:
        A page the HTML reader can parse.
    """
    body = re.sub(r"^<\?xml[^>]*\?>\s*", "", xhtml.strip())
    body = re.sub(r"^<!DOCTYPE[^>]*>\s*", "", body, flags=re.I)
    body = body.replace(' xmlns="http://www.w3.org/1999/xhtml"', "", 1)
    body = body.replace(' xmlns:epub="http://www.idpf.org/2007/ops"', "", 1)
    body = re.sub(r"\sepub:type=\"[^\"]*\"", "", body)
    style = f'<style id="caissa-props">{_css_cdata(generated_css)}</style>'
    return body.replace("</head>", f"{style}</head>", 1)


def _metadata_from_opf(package: Any) -> DocumentMetadata:
    """Rebuild document metadata from the package document.

    Args:
        package: The parsed ``<package>`` element.

    Returns:
        The metadata.
    """
    from caissa.core.model import Contributor

    dc = "{http://purl.org/dc/elements/1.1/}"
    opf = "{http://www.idpf.org/2007/opf}"

    def text(tag: str) -> str | None:
        element = package.find(f".//{dc}{tag}")
        return element.text if element is not None else None

    titles = [
        element.text or "" for element in package.iter(f"{dc}title")
    ]
    subtitle: str | None = None
    for element in package.iter(f"{opf}meta"):
        if element.get("property") == "title-type" and (element.text or "").strip() == "subtitle":
            refines = (element.get("refines") or "").lstrip("#")
            match = package.find(f'.//{dc}title[@id="{refines}"]')
            if match is not None:
                subtitle = match.text

    contributors: list[Contributor] = []
    for element in package.iter(f"{dc}creator"):
        contributors.append(
            Contributor(name=element.text or "", role=ContributorRole.AUTHOR)
        )
    for element in package.iter(f"{dc}contributor"):
        contributors.append(
            Contributor(name=element.text or "", role=ContributorRole.CONTRIBUTOR)
        )

    identifiers = [element.text or "" for element in package.iter(f"{dc}identifier")]
    isbn = next(
        (value.split("urn:isbn:")[-1] for value in identifiers if "urn:isbn:" in value), None
    )
    primary = next((value for value in identifiers if "urn:isbn:" not in value), None)
    minted = any(
        meta.get("property") == "caissa:minted-identifier"
        and (meta.text or "").strip() == "1"
        for meta in package.iter("{http://www.idpf.org/2007/opf}meta")
    )
    if minted:
        # The identifier was ours, not the author's; handing it back would put
        # a UUID in a field they deliberately left empty.
        primary = None

    return DocumentMetadata(
        title=(titles[0] if titles else ""),
        subtitle=subtitle,
        contributors=tuple(contributors),
        language=text("language") or "pt-BR",
        identifier=primary,
        isbn=isbn,
        publisher=text("publisher"),
        description=text("description"),
        publication_date=text("date"),
        rights=text("rights"),
        source=text("source"),
        subjects=tuple(element.text or "" for element in package.iter(f"{dc}subject")),
    )
