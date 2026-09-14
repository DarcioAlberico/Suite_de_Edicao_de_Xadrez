"""The five capability tables: what each format can and cannot carry.

SPEC section 5.2 gives an eight-row summary table with "sim" in almost every
cell. That table is a promise; this module is the accounting. It answers, field
by field for all forty-seven run properties and all twenty-four paragraph
properties, what actually happens on the way out -- and it does so in a form the
exporters *execute* and the tests *assert against*, so the answer cannot drift
from the code.

Reading a row
-------------
``full()``
    The reader sees exactly what the author asked for.
``approximate(detail)``
    It survives, visibly, but not exactly. Tracking rounded to the twip; a CMYK
    ink converted to sRGB.
``substitute(detail, replacement)``
    A different mechanism stands in. Real small caps faked by scaling capitals;
    a named style flattened to direct formatting.
``unsupported(detail)``
    The format has nowhere to put it. It is gone, and the report says so.

Every ``detail`` is written for the user, in Brazilian Portuguese, and names the
*mechanism* -- "w:highlight tem apenas 16 cores fixas" -- because a user who
knows why can decide whether to care.

Where the honesty is uncomfortable
----------------------------------
Three entries are worth reading before trusting any of the others, because they
are the ones a vendor would have been tempted to leave out:

* ``ligatures`` and ``font_features`` are **unsupported in PDF**. Our PDF writer
  places glyphs from the font's own ``cmap`` and ``hmtx``; it does not run an
  OpenType shaper, so a discretionary ligature requested in the IR does not
  appear. Every other format hands the job to a renderer that does shape.
* ``font_fallbacks`` is **unsupported in DOCX**. OOXML's ``w:rFonts`` has slots
  for scripts, not a CSS-style cascade of alternatives.
* ``opacity`` is **unsupported in DOCX** and only approximated in LaTeX.

Those are real holes. They are declared here so that the export report names
them at the exact paragraph they bite, rather than a reader discovering them.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from caissa.core.model import Color, ColorSpace
from caissa.export.base import (
    FormatProfile,
    PropertySupport,
    approximate,
    full,
    substitute,
    unsupported,
)

__all__ = [
    "DOCX_PROFILE",
    "EPUB_PROFILE",
    "HTML_PROFILE",
    "LATEX_PROFILE",
    "PDF_PROFILE",
    "PROFILES",
    "profile_for",
]


# --------------------------------------------------------------------------- #
# Node fields
# --------------------------------------------------------------------------- #
# A node field is a property by another name, and SPEC section 5.2's golden rule
# applies to it just the same. These are the fields that exist so the *user* can
# audit the recognition -- which page the diagram was cut from, how sure the
# classifier was about each square -- and that no book format has a place for.
# They survive only in the IR sidecar, and every export says so out loud.
_AUDIT_FIELDS: Mapping[str, PropertySupport] = {
    "diagram.solution": substitute(
        "A solucao do diagrama viaja como PGN; os lances voltam iguais, a "
        "identidade dos nos e recriada na leitura.",
        "PGN",
    ),
    "diagram.style": substitute(
        "O estilo do diagrama (tema, moldura, coordenadas) virou geometria no "
        "proprio desenho; o objeto de estilo nao volta do arquivo.",
        "geometria desenhada",
    ),
    "document.styles": substitute(
        "A folha de estilos do IR virou CSS gerado; os nomes voltam, o objeto "
        "StyleSheet nao.",
        "CSS gerado",
    ),
    "document.settings": unsupported(
        "As preferencias de edicao (idioma da notacao, figurino, fonte de xadrez) "
        "sao estado do editor e nao tem lugar no arquivo publicado."
    ),
    "document.resources": unsupported(
        "A tabela de recursos e um indice interno do IR; o arquivo publicado "
        "referencia os recursos diretamente."
    ),
    "*.provenance": unsupported(
        "A proveniencia (arquivo, pagina, retangulo, DPI) e metadado de "
        "auditoria do IR; nenhum formato de livro tem onde guarda-la."
    ),
    "diagram.source": unsupported(
        "O recorte de origem do diagrama (pagina e retangulo no PDF) nao "
        "sobrevive fora do IR."
    ),
    "diagram.recognition": unsupported(
        "A confianca por casa e o modelo que reconheceu a posicao sao dados de "
        "auditoria; o arquivo exportado guarda o FEN, nao como se chegou a ele."
    ),
    "diagram.verified_by_human": unsupported(
        "O selo de revisao humana e estado do editor, nao do livro."
    ),
    "diagram.move_context": unsupported(
        "O lance que originou o diagrama e um vinculo interno do IR."
    ),
    "document.provenance": unsupported(
        "A proveniencia do documento e metadado de auditoria do IR."
    ),
}


# --------------------------------------------------------------------------- #
# Node types DOCX has no element for
# --------------------------------------------------------------------------- #
# OOXML is flat. There is no element for "emphasis"; there is a run with
# ``w:i`` on it. The wrapper is therefore *gone* from the file -- what survives
# is its meaning, applied to every run it contained. That is a substitution and
# not a loss, but it is a substitution the user must be told about, because it
# is why reopening a DOCX gives back a document with fewer nodes than went in.
_DOCX_NODES: Mapping[str, PropertySupport] = {
    "emphasis": substitute("OOXML nao tem no de enfase; virou w:i em cada execucao.", "w:i"),
    "strong": substitute("OOXML nao tem no de negrito; virou w:b em cada execucao.", "w:b"),
    "underline": substitute(
        "OOXML nao tem no de sublinhado; virou w:u em cada execucao interna.",
        "w:u",
    ),
    "strike": substitute(
        "OOXML nao tem no de tachado; virou w:strike em cada execucao interna.",
        "w:strike",
    ),
    "small_caps": substitute(
        "OOXML nao tem no de versalete; virou w:smallCaps em cada execucao interna.",
        "w:smallCaps",
    ),
    "superscript": substitute(
        "OOXML nao tem no de sobrescrito; virou w:vertAlign=superscript na execucao.",
        "w:vertAlign",
    ),
    "subscript": substitute(
        "OOXML nao tem no de subscrito; virou w:vertAlign=subscript na execucao.",
        "w:vertAlign",
    ),
    "span": substitute("Um Span sem semantica propria some ao virar execucoes.", "w:r"),
    "link": substitute(
        "Virou w:hyperlink; o no de ligacao em si nao existe no OOXML.",
        "w:hyperlink",
    ),
    "move": substitute(
        "O lance virou texto na execucao. A notacao volta igual; o objeto Move, com o FEN anterior "
        "e os NAGs, nao.",
        "texto",
    ),
    "piece_glyph": substitute(
        "O figurino virou o glifo correspondente na fonte de xadrez do documento.",
        "texto",
    ),
    "nag_symbol": substitute(
        "O NAG virou o simbolo textual correspondente; o codigo numerico nao volta.",
        "texto",
    ),
    "math_inline": substitute(
        "A formula virou o proprio LaTeX em fonte matematica; a conversao para OMML nao esta "
        "implementada.",
        "texto",
    ),
    "math_block": substitute(
        "A formula virou o proprio LaTeX em fonte matematica; a conversao para OMML nao esta "
        "implementada.",
        "texto",
    ),
    "inline_diagram": substitute(
        "O diagrama em linha virou uma imagem EMF ancorada na execucao; a posicao FEN nao volta do "
        "DOCX.",
        "w:drawing",
    ),
    "diagram": substitute(
        "O diagrama virou um desenho EMF com legenda; a posicao continua legivel "
        "no arquivo, mas o no Diagram (FEN, marcas, proveniencia) nao volta do DOCX.",
        "w:drawing + legenda",
    ),
    "game_score": substitute(
        "A partida virou texto PGN em um paragrafo; a arvore de lances nao volta do DOCX.",
        "texto PGN",
    ),
    "anchor": substitute(
        "A ancora virou um bookmark do Word, que e como o OOXML nomeia um destino.",
        "w:bookmarkStart",
    ),
    "index_entry": substitute(
        "A entrada remissiva virou um campo XE, que o indice do Word le para se montar.",
        "campo XE",
    ),
    "quote": substitute(
        "A citacao virou paragrafos no estilo Quote; o bloco que os agrupava nao existe no OOXML.",
        "estilo Quote",
    ),
    "callout": substitute(
        "O destaque virou paragrafos no estilo Callout; o bloco que os agrupava nao existe no "
        "OOXML.",
        "estilo Callout",
    ),
    "group": substitute(
        "O grupo virou os paragrafos que continha; OOXML nao tem um bloco que agrupe outros "
        "blocos.",
        "paragrafos",
    ),
    "figure": substitute(
        "A figura virou o seu conteudo seguido de uma legenda numerada por campo SEQ.",
        "SEQ",
    ),
    "list_block": substitute(
        "A lista virou paragrafos com w:numPr, que e como o Word marca um item de lista.",
        "w:numPr",
    ),
    "list_item": substitute(
        "O item virou paragrafos com w:numPr, que e como o Word marca um item de lista.",
        "w:numPr",
    ),
    "footnote": substitute(
        "A nota de rodape foi para word/footnotes.xml, fora do corpo do documento; "
        "no lugar dela ficou um marcador que guarda a posicao. CT_FtnEdn e uma "
        "sequencia de paragrafos com w:type e w:id e mais nada, entao a formatacao "
        "do bloco de nota (alinhamento, recuo, direcao) nao tem elemento proprio ali: "
        "cada paragrafo da nota leva a sua.",
        "w:footnote",
    ),
    "endnote": substitute(
        "A nota de fim foi para word/endnotes.xml, fora do corpo do documento; no "
        "lugar dela ficou um marcador que guarda a posicao. CT_FtnEdn nao tem "
        "formatacao de bloco, entao a do no de nota nao e gravada.",
        "w:endnote",
    ),
    "note_ref": substitute(
        "A chamada de nota virou w:footnoteReference, que o Word numera sozinho.",
        "w:footnoteReference",
    ),
    "table_of_contents": substitute(
        "O sumario virou um campo TOC vivo, que o Word preenche ao abrir o arquivo.",
        "campo TOC",
    ),
    "section_break": substitute(
        "A quebra de secao virou w:sectPr, que o Word aplica ao trecho anterior.",
        "w:sectPr",
    ),
    "page_break": substitute(
        "A quebra de pagina virou w:br do tipo page dentro de um paragrafo vazio.",
        "w:br",
    ),
    "thematic_break": substitute(
        "A linha virou a borda inferior de um paragrafo vazio, que e como o Word desenha um "
        "filete.",
        "w:pBdr",
    ),
    "line_break": substitute(
        "A quebra de linha virou w:br dentro da execucao que a continha.",
        "w:br",
    ),
    "non_breaking_space": substitute(
        "O espaco inquebravel virou o proprio caractere U+00A0 no texto.",
        "texto",
    ),
    "space": substitute("O espaco virou o proprio caractere no texto da execucao.", "texto"),
    "tab": substitute(
        "O tabulador virou w:tab, que o Word posiciona pela regua do paragrafo.",
        "w:tab",
    ),
    "image_inline": full(),
    "image_block": full(),
    "code_block": substitute(
        "O bloco de codigo virou paragrafos no estilo Code, um paragrafo por linha.",
        "estilo Code",
    ),
    "raw_inline": unsupported("Um RawInline de outro formato nao tem equivalente no DOCX."),
    "raw_passthrough": unsupported(
        "Um RawPassthrough de outro formato nao tem equivalente no DOCX."
    ),
}


def _colour_space(value: Any) -> str:
    """Key a colour by its colour space.

    Args:
        value: A :class:`~caissa.core.model.props.Color`, or anything else.

    Returns:
        The space name, or ``"rgb"`` for a non-colour.
    """
    if isinstance(value, Color):
        return value.space.value
    return ColorSpace.RGB.value


def _colour(
    *,
    cmyk: PropertySupport,
    spot: PropertySupport,
) -> PropertySupport:
    """Build a colour support entry that discriminates by colour space.

    Args:
        cmyk: What happens to a CMYK ink.
        spot: What happens to a spot colour.

    Returns:
        The support entry.
    """
    return PropertySupport(
        by_value={ColorSpace.CMYK.value: cmyk, ColorSpace.SPOT.value: spot},
        value_key=_colour_space,
    )


def _with_exceptions(default: PropertySupport, lossless: tuple[str, ...]) -> PropertySupport:
    """Build an entry that is lossy in general but exact for a few values.

    Args:
        default: What happens to a value not named in ``lossless``.
        lossless: The values the format does carry exactly.

    Returns:
        The support entry.
    """
    return PropertySupport(
        capability=default.capability,
        detail=default.detail,
        replacement=default.replacement,
        by_value={value: full() for value in lossless},
    )


def _weight_by_value(other: PropertySupport) -> PropertySupport:
    """Build a font-weight entry for formats that only know regular and bold.

    Args:
        other: What happens to a weight that is neither 400 nor 700.

    Returns:
        The support entry.
    """
    return PropertySupport(
        capability=other.capability,
        detail=other.detail,
        replacement=other.replacement,
        by_value={"400": full(), "700": full()},
    )


# Every place OOXML writes an author's colour -- ``w:color``, ``w:shd/@w:fill``,
# ``w:u/@w:color``, ``w:tcBorders`` -- is typed ``ST_HexColor``: six hexadecimal
# digits of sRGB, or the word ``auto``. There is no colour space in it, so the
# question a colour asks of DOCX is never "which colour" but "which colour
# space", and the answer is the same for all four elements.
_DOCX_COLOUR = PropertySupport(
    by_value={
        ColorSpace.CMYK.value: approximate(
            "ST_HexColor tem seis digitos de sRGB e nenhum espaco de cor; a tinta "
            "CMYK foi convertida.",
            "sRGB",
        ),
        ColorSpace.SPOT.value: substitute(
            "OOXML nao tem cor especial; a cor alternativa da tinta foi gravada em sRGB.",
            "sRGB",
        ),
        ColorSpace.GRAY.value: approximate(
            "ST_HexColor tem tres canais; um cinza de canal unico volta como tres "
            "canais iguais, com o mesmo tom e outra identidade.",
            "sRGB",
        ),
        ColorSpace.NAMED.value: substitute(
            "OOXML nao guarda o nome que o autor deu a cor; so o valor sRGB "
            "correspondente foi gravado.",
            "sRGB",
        ),
    },
    value_key=_colour_space,
)


# --------------------------------------------------------------------------- #
# DOCX
# --------------------------------------------------------------------------- #
_DOCX_RUN: Mapping[str, PropertySupport] = {
    "font_size": approximate(
        "w:sz guarda o corpo em meios-pontos inteiros; um corpo de 10,4 pt sai "
        "como 10,5 pt.",
        "meio-ponto mais proximo",
    ),
    "letter_spacing": approximate(
        "w:spacing e em twips inteiros; o tracking foi arredondado ao twip.",
        "twip mais proximo",
    ),
    "baseline_shift": approximate(
        "w:position guarda o deslocamento vertical em meios-pontos inteiros.",
        "meio-ponto mais proximo",
    ),
    "horizontal_scale": approximate(
        "w:w guarda a escala horizontal como um percentual inteiro.",
        "percentual inteiro",
    ),
    "background": substitute(
        "OOXML nao tem fundo de execucao com alfa; virou w:shd solido em sRGB.",
        "w:shd",
    ),
    "underline_color": approximate(
        "w:u/@w:color e sempre sRGB; uma tinta CMYK ou especial foi convertida.",
        "sRGB",
    ),
    "kerning_min_size": approximate(
        "w:kern guarda o corpo minimo para kerning em meios-pontos inteiros.",
        "meio-ponto mais proximo",
    ),
    "font_fallbacks": unsupported(
        "w:rFonts nomeia uma familia por script, nao uma lista de alternativas; "
        "so a familia principal e gravada."
    ),
    "font_weight": _weight_by_value(
        approximate(
            "OOXML so distingue normal de negrito (w:b); pesos intermediarios nao existem.",
            "negrito quando >= 600, normal caso contrario",
        )
    ),
    "oblique_angle": unsupported(
        "Word nao tem inclinacao sintetica com angulo; use uma face italica de verdade."
    ),
    "font_stretch": unsupported("OOXML nao tem classe de largura; use uma familia condensada."),
    "color": _DOCX_COLOUR,
    "highlight": approximate(
        "w:highlight tem apenas 16 cores fixas; a mais proxima foi usada.",
        "cor mais proxima da paleta do Word",
    ),
    "word_spacing": unsupported("OOXML nao tem espacamento de palavra por execucao."),
    "font_features": unsupported(
        "OOXML expoe apenas ligaduras e formas numericas (w14); tags OpenType arbitrarias nao."
    ),
    "variation_axes": substitute(
        "DOCX so embute instancias estaticas de fontes variaveis.",
        "instancia estatica na coordenada pedida",
    ),
    "small_caps": PropertySupport(
        by_value={
            "none": full(),
            "synthetic": full(),
            "real": substitute(
                "w:smallCaps e sintetico: o Word reduz as maiusculas em vez de usar o "
                "conjunto 'smcp' da fonte.",
                "versalete sintetico",
            ),
            "petite": substitute(
                "O Word nao tem versalete miudo; foi usado o versalete sintetico comum.",
                "versalete sintetico",
            ),
            "unicase": unsupported(
                "O Word nao tem a forma unicase; as maiusculas e minusculas ficam como estao."
            ),
        }
    ),
    "text_transform": PropertySupport(
        by_value={
            "none": full(),
            "uppercase": substitute(
                "Gravado como w:caps, que e uma transformacao de exibicao.",
                "w:caps",
            ),
            "lowercase": unsupported(
                "OOXML nao tem transformacao para minusculas; o texto sai como foi digitado."
            ),
            "capitalize": unsupported(
                "OOXML nao tem transformacao para capitalizacao; o texto sai como foi digitado."
            ),
            "full-width": unsupported(
                "OOXML nao tem transformacao para largura plena; o texto sai como foi digitado."
            ),
        }
    ),
    "rise_relative": substitute(
        "w:position e absoluto (meio-ponto); o deslocamento relativo foi convertido "
        "usando o corpo do texto.",
        "w:position em meios-pontos",
    ),
    "vertical_align": PropertySupport(
        by_value={
            "baseline": full(),
            "superscript": full(),
            "subscript": full(),
            "top": unsupported(
                "w:vertAlign so tem sobrescrito e subscrito; os demais alinhamentos verticais nao "
                "existem."
            ),
            "middle": unsupported(
                "w:vertAlign so tem sobrescrito e subscrito; os demais alinhamentos verticais nao "
                "existem."
            ),
            "bottom": unsupported(
                "w:vertAlign so tem sobrescrito e subscrito; os demais alinhamentos verticais nao "
                "existem."
            ),
            "text-top": unsupported(
                "w:vertAlign so tem sobrescrito e subscrito; os demais alinhamentos verticais nao "
                "existem."
            ),
            "text-bottom": unsupported(
                "w:vertAlign so tem sobrescrito e subscrito; os demais alinhamentos verticais nao "
                "existem."
            ),
        }
    ),
    "underline_thickness": unsupported(
        "w:u nao tem espessura propria; a linha sai na espessura padrao do Word."
    ),
    "underline_offset": unsupported(
        "w:u nao tem deslocamento proprio; a linha sai na posicao padrao do Word."
    ),
    "underline_skip_ink": unsupported("O Word sempre interrompe o sublinhado nos descendentes."),
    "strikethrough_color": unsupported(
        "w:strike usa sempre a cor do texto; uma cor propria de tachado nao existe."
    ),
    "overline": unsupported(
        "OOXML nao tem sobrelinha de execucao; so existe como borda de paragrafo."
    ),
    "outline": approximate(
        "w:outline e um interruptor: nao aceita espessura nem cor de traco.",
        "contorno padrao do Word",
    ),
    "shadow": approximate(
        "w:shadow e um interruptor: nao aceita deslocamento, desfoque nem cor.",
        "sombra padrao do Word",
    ),
    "opacity": unsupported(
        "OOXML nao tem opacidade de execucao; um texto meio transparente sai opaco."
    ),
    "hyphenate": unsupported(
        "A hifenizacao no Word e do paragrafo (w:suppressAutoHyphens), nao da execucao."
    ),
    "no_break": unsupported(
        "OOXML nao impede a quebra dentro de uma execucao; use espaco inquebravel."
    ),
}

_DOCX_PARAGRAPH: Mapping[str, PropertySupport] = {
    "style": approximate(
        "Todo paragrafo no Word tem um estilo. Os paragrafos que nao nomeavam um "
        "receberam o estilo do seu papel (Diagram, Callout, Code...), entao o "
        "campo volta preenchido onde antes estava vazio.",
        "estilo do papel do bloco",
    ),
    "line_spacing": approximate(
        "w:spacing/@w:line guarda a entrelinha em 240-avos de linha ou em twips inteiros.",
        "arredondado ao twip",
    ),
    "space_before": approximate(
        "w:spacing/@w:before guarda o espaco antes do paragrafo em twips inteiros.",
        "twip",
    ),
    "space_after": approximate(
        "w:spacing/@w:after guarda o espaco depois do paragrafo em twips inteiros.",
        "twip",
    ),
    "indent_left": approximate("w:ind/@w:left guarda o recuo esquerdo em twips inteiros.", "twip"),
    "indent_right": approximate("w:ind/@w:right guarda o recuo direito em twips inteiros.", "twip"),
    "indent_first_line": approximate(
        "w:ind/@w:firstLine guarda o recuo da primeira linha em twips inteiros.",
        "twip",
    ),
    "borders": approximate(
        "w:pBdr guarda a espessura em oitavos de ponto e a cor em sRGB.",
        "oitavo de ponto + sRGB",
    ),
    "shading": approximate(
        "w:shd guarda o sombreado sempre em sRGB opaco, sem canal alfa.",
        "sRGB",
    ),
    "direction": full(),
    "padding": approximate(
        "O espacamento de borda do paragrafo no Word e por lado, em pontos inteiros.",
        "w:pBdr/@w:space arredondado ao ponto",
    ),
    "tab_stops": approximate(
        "w:tab/@w:pos e ST_SignedTwipsMeasure: um inteiro em vigesimos de ponto. "
        "A regua volta com as mesmas paradas, o mesmo alinhamento e o mesmo "
        "preenchimento, e cada posicao arredondada ao twip; uma parada medida em "
        "em, rem ou porcentagem nao tem unidade na regua do Word e volta em zero.",
        "twip",
    ),
    "default_run": substitute(
        "OOXML nao tem um registro de formatacao de execucao no nivel do paragrafo: "
        "w:pPr/w:rPr e a formatacao da marca de paragrafo, nao das execucoes. As "
        "propriedades padrao do paragrafo foram escritas em cada w:r que ele contem, "
        "entao o texto sai igual e a heranca deixa de existir como tal.",
        "propriedades em cada w:r",
    ),
}

_DOCX_FEATURES: Mapping[str, PropertySupport] = {
    "vector_diagram": full(),
    "images": substitute(
        "A imagem cujo arquivo nao esta ao alcance virou um quadro de reserva cinza do tamanho "
        "pedido, com a chave do recurso no nome da figura; com o arquivo, ela e embutida.",
        "quadro de reserva",
    ),
    "named_styles": full(),
    "footnotes": full(),
    "endnotes": full(),
    "auto_numbering": full(),
    "toc_field": full(),
    "columns": full(),
    "page_geometry": full(),
    "headers_footers": full(),
    "drop_cap": substitute(
        "A capitular foi gravada como quadro de texto ancorado (w:framePr).",
        "w:framePr com w:dropCap",
    ),
    "math": substitute(
        "A formula foi gravada como o proprio LaTeX em fonte monoespacada; a conversao "
        "para OMML nao esta implementada.",
        "texto LaTeX literal",
    ),
    "index_entry": full(),
    "interactive_replay": unsupported(
        "DOCX nao tem conteudo interativo; a navegacao pela partida so existe em HTML."
    ),
    "dark_mode": unsupported("DOCX nao tem tema escuro; as cores gravadas sao as do modo claro."),
    "font_embedding": approximate(
        "O Word so aceita fontes embutidas no formato obfuscado da Microsoft (fontTable + "
        "odttf); a fonte foi referenciada pelo nome e nao embutida.",
        "referencia por nome de familia",
    ),
    "accessibility_tags": full(),
    "raw_passthrough": unsupported(
        "Um bloco RawPassthrough de outro formato nao tem equivalente no DOCX."
    ),
    "fixed_layout": unsupported("DOCX e reflowable por natureza; nao ha layout fixo para gravar."),
}


# --------------------------------------------------------------------------- #
# Node fields DOCX carries differently, or not at all
# --------------------------------------------------------------------------- #
# These are the fields where the honest answer is about ECMA-376 and not about
# this writer: the movetext has no room for a position, ``w:tblHeader`` is one
# flag where the IR has three, and ``CT_TcPr`` simply has no horizontal
# alignment. Each entry names the element it is talking about so that a reviewer
# can check it against the schema rather than against us.
_DOCX_NODE_FIELDS: Mapping[str, PropertySupport] = {
    "image_block.width": approximate(
        "wp:extent guarda a largura da figura em EMU inteiros e absolutos; uma medida "
        "relativa (%, em) ou negativa vira o tamanho intrinseco da imagem.",
        "EMU",
    ),
    "image_block.height": approximate(
        "wp:extent guarda a altura da figura em EMU inteiros e absolutos; uma medida "
        "relativa (%, em) ou negativa vira o tamanho intrinseco da imagem.",
        "EMU",
    ),
    "image_block.crop": approximate(
        "a:srcRect guarda o corte em milesimos de porcento de cada borda.",
        "a:srcRect",
    ),
    "image_inline.width": approximate(
        "wp:extent guarda a largura da figura em EMU inteiros e absolutos; uma medida "
        "relativa (%, em) ou negativa vira o tamanho intrinseco da imagem.",
        "EMU",
    ),
    "image_inline.height": approximate(
        "wp:extent guarda a altura da figura em EMU inteiros e absolutos; uma medida "
        "relativa (%, em) ou negativa vira o tamanho intrinseco da imagem.",
        "EMU",
    ),
    "image_inline.baseline_shift": unsupported(
        "wp:inline ancora a figura na linha de base e nao tem deslocamento vertical; "
        "so wp:anchor teria, e ele tira a figura do fluxo do texto."
    ),
    "document.metadata": approximate(
        "docProps/core.xml carrega o Dublin Core que o Word mostra: titulo, "
        "assunto, descricao, idioma, autores, palavras-chave, identificador e "
        "datas. O papel de cada contribuidor, o nome de ordenacao e os campos de "
        "publicacao (ISBN, editora, edicao, serie, direitos, capa) so caberiam em "
        "docProps/custom.xml como texto solto e este exportador nao os grava.",
        "Dublin Core de docProps/core.xml",
    ),
    "heading.numbering_text": substitute(
        "O numero do titulo virou texto literal seguido de tabulacao na propria "
        "execucao, que e como o Word mostra um titulo numerado a mao; ao reler, ele "
        "e parte do texto do titulo e nao um campo separado.",
        "texto + w:tab",
    ),
    "heading.toc_text": substitute(
        "O campo TOC monta o sumario a partir do texto do proprio titulo. Um texto "
        "abreviado so existiria como campo TC em cada titulo, com o comutador \\f no "
        "TOC, e este exportador nao os grava.",
        "texto do proprio titulo",
    ),
    "move_node.position_before": unsupported(
        "O movetext do PGN guarda lances, nao posicoes: o FEN antes do lance e "
        "recalculado por quem le a partida, e nao existe em lugar nenhum do arquivo."
    ),
    "move_node.position_after": unsupported(
        "O movetext do PGN guarda lances, nao posicoes: o FEN depois do lance e "
        "recalculado por quem le a partida, e nao existe em lugar nenhum do arquivo."
    ),
    "move_node.uci": unsupported(
        "A forma longa (e2e4) e derivada do lance e da posicao; o movetext grava a "
        "notacao algebrica abreviada, que e o que o leitor ve."
    ),
    "move_node.arrows": approximate(
        "O comando [%cal] do PGN tem quatro letras de cor -- verde, vermelho, "
        "amarelo e azul. Uma seta em CMYK, especial ou em qualquer outro tom volta "
        "na cor da letra mais proxima.",
        "quatro cores do [%cal]",
    ),
    "move_node.highlights": approximate(
        "O comando [%csl] do PGN tem quatro letras de cor; uma casa marcada em "
        "outro tom volta na cor da letra mais proxima.",
        "quatro cores do [%csl]",
    ),
    "move_node.evaluation": approximate(
        "O comando [%eval] do PGN carrega um texto so. O tipo (centipeoes ou mate) "
        "e a profundidade sao reconstruidos a partir dele, entao uma avaliacao cujo "
        "texto nao concorda com os campos volta como o texto diz.",
        "texto do [%eval]",
    ),
    "table.columns": approximate(
        "w:gridCol/@w:w guarda a largura de cada coluna em twips inteiros; uma "
        "coluna medida em em, rem ou porcentagem nao tem unidade na grade do Word. "
        "E w:tblGrid e obrigatorio no OOXML, entao uma tabela que nao descrevia as "
        "suas colunas volta com uma coluna por coluna da grade.",
        "twip",
    ),
    "table.borders": approximate(
        "w:tblBorders guarda a espessura em oitavos de ponto, o afastamento em "
        "pontos inteiros e a cor em sRGB.",
        "oitavo de ponto + sRGB",
    ),
    "table.cell_padding": approximate(
        "w:tblCellMar guarda a margem interna das celulas em twips inteiros.",
        "twip",
    ),
    "table.width": approximate(
        "w:tblW e twips inteiros (dxa) ou cinquentavos de porcento (pct); uma "
        "largura em em ou rem nao tem unidade ali e a tabela sai automatica.",
        "twip ou cinquentavo de porcento",
    ),
    "table.alignment": approximate(
        "w:tblPr/w:jc so tem esquerda, centro e direita; justificado, distribuido e "
        "os alinhamentos logicos viram o alinhamento a esquerda.",
        "esquerda, centro ou direita",
    ),
    "table.repeat_header": substitute(
        "OOXML tem um unico interruptor, w:tblHeader por linha, que diz ao mesmo "
        "tempo 'esta linha e cabecalho' e 'repita-a a cada pagina'. As tres decisoes "
        "que o IR guarda separadas voltam como essa unica.",
        "w:tblHeader",
    ),
    "table.header_row_count": substitute(
        "Nao existe contagem de linhas de cabecalho no OOXML: o numero e derivado "
        "das linhas marcadas com w:tblHeader.",
        "contagem derivada de w:tblHeader",
    ),
    "table.number": substitute(
        "O numero da tabela virou um campo SEQ, que o Word renumera sozinho ao "
        "abrir; o valor gravado no IR nao volta porque quem manda passa a ser o campo.",
        "campo SEQ",
    ),
    "table.caption": substitute(
        "OOXML nao tem elemento de legenda de tabela com conteudo formatado: "
        "w:tblCaption e uma cadeia de texto. A legenda virou um paragrafo no estilo "
        "Caption, numerado por campo SEQ, e deixou de pertencer a tabela.",
        "paragrafo no estilo Caption",
    ),
    "table.caption_above": substitute(
        "Como a legenda virou um paragrafo vizinho, o lado em que ela fica e a ordem "
        "dos paragrafos e nao um campo da tabela.",
        "ordem dos paragrafos",
    ),
    "table_row.height": approximate(
        "w:trHeight guarda a altura da linha em twips inteiros; uma altura em ex ou "
        "em nao tem unidade ali.",
        "twip",
    ),
    "table_row.repeat_on_break": substitute(
        "OOXML tem um unico interruptor, w:tblHeader, para 'linha de cabecalho' e "
        "'repete a cada pagina'; as duas decisoes voltam como uma.",
        "w:tblHeader",
    ),
    "table_cell.alignment": unsupported(
        "CT_TcPr tem w:vAlign e nao tem alinhamento horizontal: no OOXML o "
        "alinhamento horizontal e sempre do paragrafo (w:pPr/w:jc). Aplica-lo aos "
        "paragrafos da celula reescreveria uma decisao que o autor tomou na celula, "
        "entao ele nao e gravado."
    ),
    "table_cell.is_header": substitute(
        "OOXML marca cabecalho por linha (w:tblHeader) e nao por celula; uma celula "
        "de cabecalho numa linha comum nao tem como ser gravada.",
        "w:tblHeader da linha",
    ),
    "table_cell.padding": approximate(
        "w:tcMar guarda a margem interna da celula em twips inteiros; uma margem em "
        "rem, em ou porcentagem nao tem unidade ali.",
        "twip",
    ),
    "table_cell.borders": approximate(
        "w:tcBorders guarda a espessura em oitavos de ponto, o afastamento em pontos "
        "inteiros e a cor em sRGB.",
        "oitavo de ponto + sRGB",
    ),
    "table_cell.shading": _DOCX_COLOUR,
}


DOCX_PROFILE = FormatProfile(
    name="docx",
    run=_DOCX_RUN,
    paragraph=_DOCX_PARAGRAPH,
    nodes=_DOCX_NODES,
    features=_DOCX_FEATURES,
    node_fields={**_AUDIT_FIELDS, **_DOCX_NODE_FIELDS},
    vector_diagrams=True,
)


# --------------------------------------------------------------------------- #
# HTML / EPUB (CSS)
# --------------------------------------------------------------------------- #
_CSS_RUN: Mapping[str, PropertySupport] = {
    "color": _colour(
        cmyk=approximate("CSS e sRGB; a tinta CMYK foi convertida.", "sRGB"),
        spot=substitute("CSS nao tem cor especial; a cor alternativa foi gravada.", "sRGB"),
    ),
    "highlight": _colour(
        cmyk=approximate("CSS e sRGB; a tinta CMYK foi convertida.", "sRGB"),
        spot=substitute("CSS nao tem cor especial; a cor alternativa foi gravada.", "sRGB"),
    ),
    "background": _colour(
        cmyk=approximate("CSS e sRGB; a tinta CMYK foi convertida.", "sRGB"),
        spot=substitute("CSS nao tem cor especial; a cor alternativa foi gravada.", "sRGB"),
    ),
    "kerning_min_size": unsupported(
        "CSS liga ou desliga o kerning (font-kerning); nao ha limiar por corpo."
    ),
    "horizontal_scale": approximate(
        "CSS nao escala glifos horizontalmente sem transformar a caixa; foi usada uma "
        "combinacao de font-stretch e transform, que nao reflui igual.",
        "font-stretch + transform: scaleX",
    ),
    "small_caps": PropertySupport(
        by_value={
            "none": full(),
            "real": full(),
            "petite": full(),
            "unicase": full(),
            "synthetic": substitute(
                "O pedido explicito de versalete sintetico virou font-variant-caps com "
                "font-synthesis: small-caps; o resultado depende do leitor.",
                "font-synthesis: small-caps",
            ),
        }
    ),
    "underline": PropertySupport(
        by_value={
            "none": full(),
            "single": full(),
            "double": full(),
            "dotted": full(),
            "dashed": full(),
            "wavy": full(),
            "thick": full(),
            "dotted-heavy": approximate("CSS nao tem pontilhado grosso.", "dotted + espessura"),
            "dashed-heavy": approximate("CSS nao tem tracejado grosso.", "dashed + espessura"),
            "dash-long": approximate("CSS nao tem traco longo.", "dashed"),
            "dash-dot": approximate("CSS nao tem traco-ponto.", "dashed"),
            "dash-dot-dot": approximate("CSS nao tem traco-ponto-ponto.", "dashed"),
            "wavy-double": approximate("CSS nao tem ondulado duplo.", "wavy"),
            "wavy-heavy": approximate("CSS nao tem ondulado grosso.", "wavy + espessura"),
            "words-only": substitute(
                "CSS nao sublinha apenas palavras; os espacos foram marcados sem decoracao.",
                "spans por palavra",
            ),
        }
    ),
    "emboss": substitute(
        "CSS nao tem relevo; foi desenhado com duas sombras de texto.", "text-shadow duplo"
    ),
    "engrave": substitute(
        "CSS nao tem baixo-relevo; foi desenhado com duas sombras de texto.", "text-shadow duplo"
    ),
    "outline": approximate(
        "O traco de glifo em CSS depende de -webkit-text-stroke, que nao e padronizado; "
        "leitores sem suporte mostram o texto preenchido.",
        "-webkit-text-stroke",
    ),
    "oblique_angle": full(),
}

_CSS_NODES: Mapping[str, PropertySupport] = {
    "move_node": substitute(
        "A partida viaja como PGN, que e o formato que todo leitor de xadrez "
        "entende. Os lances, comentarios, NAGs e variantes voltam iguais; a "
        "identidade de cada lance e recriada na leitura, porque o PGN nao "
        "carrega identificadores.",
        "PGN",
    ),
    "game_score": substitute(
        "A partida viaja como PGN; o conteudo volta igual, a identidade do no e "
        "recriada.",
        "PGN",
    ),
}

_CSS_PARAGRAPH: Mapping[str, PropertySupport] = {
    "mark_props": unsupported(
        "Nao existe marca de paragrafo neste formato; a formatacao do pilcrow "
        "nao tem onde ser gravada."
    ),
    "tab_stops": substitute(
        "CSS nao tem reguas de tabulacao; as paradas viraram recuo e alinhamento.",
        "padding + text-align",
    ),
    "suppress_line_numbers": unsupported(
        "CSS nao numera linhas de paragrafo; a supressao nao tem efeito nenhum."
    ),
    "outline_level": full(),
}

_CSS_FEATURES: Mapping[str, PropertySupport] = {
    "vector_diagram": full(),
    "named_styles": full(),
    "footnotes": full(),
    "endnotes": full(),
    "auto_numbering": full(),
    "toc_field": substitute(
        "Nao ha campo de sumario; a lista foi gerada no momento da exportacao.",
        "sumario gerado",
    ),
    "columns": full(),
    "page_geometry": substitute(
        "A geometria de pagina so existe na impressao; foi gravada em @page (CSS Paged Media).",
        "@page",
    ),
    "headers_footers": approximate(
        "Cabecalhos e rodapes correntes dependem de margens @page, que poucos leitores "
        "implementam.",
        "@page @top-center / @bottom-center",
    ),
    "drop_cap": full(),
    "math": full(),
    "index_entry": substitute(
        "Nao ha remissivo automatico; as entradas viraram ancoras e uma lista no fim.",
        "ancoras + lista remissiva",
    ),
    "interactive_replay": full(),
    "dark_mode": full(),
    "font_embedding": full(),
    "accessibility_tags": full(),
    "raw_passthrough": unsupported(
        "Um bloco RawPassthrough de outro formato nao tem equivalente em XHTML."
    ),
    "fixed_layout": full(),
}


HTML_PROFILE = FormatProfile(
    name="html",
    nodes=_CSS_NODES,
    run=_CSS_RUN,
    paragraph=_CSS_PARAGRAPH,
    features=_CSS_FEATURES,
    node_fields=_AUDIT_FIELDS,
    vector_diagrams=True,
)


EPUB_PROFILE = FormatProfile(
    name="epub",
    nodes=_CSS_NODES,
    run=_CSS_RUN,
    paragraph=_CSS_PARAGRAPH,
    node_fields=_AUDIT_FIELDS,
    features={
        **_CSS_FEATURES,
        "interactive_replay": approximate(
            "Scripts em EPUB dependem do leitor; a navegacao por setas foi emitida com "
            "degradacao graciosa para leitores sem script.",
            "script opcional",
        ),
        "headers_footers": unsupported(
            "Um EPUB reflowable nao tem cabecalho nem rodape corrente; o leitor decide."
        ),
        "page_geometry": unsupported(
            "Um EPUB reflowable nao tem geometria de pagina; o leitor decide."
        ),
        "columns": approximate(
            "Colunas em EPUB reflowable dependem do leitor; foi emitido column-count.",
            "column-count",
        ),
    },
    vector_diagrams=True,
)


# --------------------------------------------------------------------------- #
# LaTeX
# --------------------------------------------------------------------------- #
_LATEX_RUN: Mapping[str, PropertySupport] = {
    "font_family": approximate(
        "A familia foi mapeada para uma familia NFSS; a fonte final depende do que esta "
        "instalado no TeX que compilar.",
        "familia NFSS equivalente",
    ),
    "font_fallbacks": unsupported("NFSS nao tem pilha de alternativas de fonte."),
    "font_weight": _weight_by_value(
        approximate(
            "NFSS tem series discretas; o peso foi mapeado para a mais proxima.",
            "serie NFSS mais proxima",
        )
    ),
    "oblique_angle": unsupported("Nao ha inclinacao sintetica com angulo em LaTeX puro."),
    "font_stretch": approximate(
        "A largura virou uma serie NFSS condensada/expandida quando a familia tem uma.",
        "serie NFSS",
    ),
    "color": _colour(
        cmyk=full(),
        spot=substitute(
            "xcolor nao tem tinta especial sem perfil; a cor alternativa foi usada.", "RGB"
        ),
    ),
    "highlight": approximate(
        "\\colorbox nao quebra entre linhas; o realce foi aplicado por trecho.", "\\colorbox"
    ),
    "background": approximate(
        "\\colorbox nao quebra entre linhas; o fundo foi aplicado por trecho.", "\\colorbox"
    ),
    "letter_spacing": approximate(
        "O microtype expressa o tracking em milesimos de em; o valor foi convertido.",
        "\\textls",
    ),
    "word_spacing": approximate("O espaco entre palavras virou \\spaceskip.", "\\spaceskip"),
    "horizontal_scale": approximate(
        "A escala horizontal virou \\scalebox, que nao reflui.", "\\scalebox"
    ),
    "kerning_min_size": unsupported("TeX nao tem limiar de corpo para kerning."),
    "font_features": approximate(
        "As tags OpenType exigem fontspec e um motor Unicode (XeLaTeX ou LuaLaTeX).",
        "\\addfontfeature{RawFeature=...}",
    ),
    "variation_axes": approximate(
        "Os eixos variaveis exigem fontspec e um motor Unicode.", "fontspec"
    ),
    "small_caps": PropertySupport(
        by_value={
            "none": full(),
            "real": full(),
            "synthetic": substitute(
                "\\textsc usa o conjunto real quando existe; o pedido explicito de sintetico "
                "nao e distinguivel.",
                "\\textsc",
            ),
            "petite": unsupported("NFSS nao tem versalete miudo."),
            "unicase": unsupported("NFSS nao tem forma unicase."),
        }
    ),
    "text_transform": PropertySupport(
        by_value={
            "none": full(),
            "uppercase": full(),
            "lowercase": full(),
            "capitalize": approximate(
                "\\MakeUppercase nao capitaliza por palavra; a transformacao foi aplicada "
                "no texto antes de escrever.",
                "texto ja transformado",
            ),
            "full-width": unsupported("LaTeX nao tem transformacao para largura plena."),
        }
    ),
    "vertical_align": PropertySupport(
        by_value={
            "baseline": full(),
            "superscript": full(),
            "subscript": full(),
            "top": unsupported("LaTeX nao alinha execucoes ao topo da linha."),
            "middle": unsupported("LaTeX nao alinha execucoes ao meio da linha."),
            "bottom": unsupported("LaTeX nao alinha execucoes a base da linha."),
            "text-top": unsupported("LaTeX nao alinha execucoes ao topo do texto."),
            "text-bottom": unsupported("LaTeX nao alinha execucoes a base do texto."),
        }
    ),
    "numeral_figure": approximate(
        "\\oldstylenums depende da familia ter algarismos antigos.", "\\oldstylenums"
    ),
    "numeral_spacing": unsupported("LaTeX nao seleciona algarismos tabulares sem fontspec."),
    "underline": _with_exceptions(
        approximate("O pacote ulem nao tem esse tipo de traco.", "\\uline"),
        ("none", "single", "double", "dotted", "dashed", "wavy"),
    ),
    "underline_color": approximate(
        "A cor do sublinhado depende de \\setulcolor do pacote soul.", "\\setulcolor"
    ),
    "underline_thickness": approximate("A espessura depende de \\setul do pacote soul.", "\\setul"),
    "underline_offset": approximate(
        "O deslocamento depende de \\setul do pacote soul.", "\\setul"
    ),
    "underline_skip_ink": unsupported("O ulem nao interrompe o traco nos descendentes."),
    "strikethrough": _with_exceptions(
        approximate("O ulem so risca uma vez.", "\\sout"), ("none", "single")
    ),
    "strikethrough_color": unsupported("\\sout usa sempre a cor do texto."),
    "overline": unsupported("Nao ha sobrelinha de texto corrido em LaTeX."),
    "outline": unsupported("Nao ha traco de glifo em LaTeX sem PSTricks."),
    "shadow": unsupported("Nao ha sombra de texto em LaTeX sem pacote grafico."),
    "emboss": unsupported("Nao ha relevo de texto em LaTeX."),
    "engrave": unsupported("Nao ha baixo-relevo de texto em LaTeX."),
    "emphasis_mark": unsupported("Nao ha marca de enfase lateral em LaTeX."),
    "opacity": approximate(
        "A opacidade exige o pacote transparent e um motor que o suporte.", "\\transparent"
    ),
    "spell_check": unsupported("LaTeX nao carrega marcacao de revisao ortografica."),
    "direction": unsupported(
        "A direcao de escrita exige bidi ou polyglossia com um motor Unicode."
    ),
    "hidden": substitute("O trecho oculto foi comentado no fonte .tex.", "comentario"),
}

_LATEX_PARAGRAPH: Mapping[str, PropertySupport] = {
    "mark_props": unsupported(
        "Nao existe marca de paragrafo neste formato; a formatacao do pilcrow "
        "nao tem onde ser gravada."
    ),
    "shading": approximate(
        "O fundo de paragrafo virou um \\colorbox de largura total.", "\\colorbox"
    ),
    "padding": approximate("O espacamento interno virou recuo e \\vspace.", "recuo + \\vspace"),
    "suppress_line_numbers": approximate(
        "A supressao de numeracao de linha depende do pacote lineno.", "\\nolinenumbers"
    ),
    "widow_control": approximate(
        "TeX controla viuvas por penalidade, nao por interruptor.", "\\widowpenalty"
    ),
    "direction": unsupported("A direcao de escrita exige bidi ou polyglossia."),
}

_LATEX_FEATURES: Mapping[str, PropertySupport] = {
    "vector_diagram": full(),
    "named_styles": substitute(
        "Cada estilo nomeado virou uma macro \\caissa<Nome>.", "macro LaTeX"
    ),
    "footnotes": full(),
    "endnotes": full(),
    "auto_numbering": full(),
    "toc_field": full(),
    "columns": full(),
    "page_geometry": full(),
    "headers_footers": full(),
    "drop_cap": full(),
    "math": full(),
    "index_entry": full(),
    "interactive_replay": unsupported("LaTeX nao tem conteudo interativo."),
    "dark_mode": unsupported("LaTeX nao tem tema escuro."),
    "font_embedding": approximate(
        "A fonte e embutida pelo motor TeX no PDF final, nao pelo .tex.", "embutida na compilacao"
    ),
    "accessibility_tags": approximate(
        "A marcacao de acessibilidade depende do PDF gerado (tagpdf / LuaLaTeX).", "tagpdf",
    ),
    "raw_passthrough": full(),
    "fixed_layout": full(),
}


LATEX_PROFILE = FormatProfile(
    name="latex",
    run=_LATEX_RUN,
    paragraph=_LATEX_PARAGRAPH,
    features=_LATEX_FEATURES,
    node_fields=_AUDIT_FIELDS,
    vector_diagrams=True,
)


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
_PDF_RUN: Mapping[str, PropertySupport] = {
    "style": substitute(
        "O PDF nao tem folha de estilos; o estilo nomeado foi resolvido em formatacao "
        "direta antes de escrever.",
        "formatacao direta equivalente",
    ),
    "font_fallbacks": approximate(
        "A alternativa e usada quando a familia principal nao esta disponivel; nao ha "
        "troca por glifo dentro da mesma execucao.",
        "primeira familia disponivel",
    ),
    "font_weight": _weight_by_value(
        approximate(
            "So os cortes realmente instalados podem ser embutidos; o peso foi mapeado "
            "para o mais proximo.",
            "corte instalado mais proximo",
        )
    ),
    "font_stretch": substitute(
        "Sem um corte estreito instalado, a largura virou escala horizontal do texto.",
        "escala horizontal (Tz)",
    ),
    "color": _colour(
        cmyk=full(),
        spot=substitute(
            "A tinta especial foi gravada como espaco Separation com alternativa CMYK.",
            "Separation com espaco alternativo",
        ),
    ),
    "kerning": approximate(
        "O kerning vem da tabela 'kern' da fonte; o posicionamento GPOS nao e interpretado.",
        "pares da tabela kern",
    ),
    "ligatures": unsupported(
        "O escritor de PDF posiciona glifos pelo cmap da fonte e nao executa um "
        "conformador OpenType; ligaduras pedidas nao sao formadas."
    ),
    "font_features": unsupported(
        "O escritor de PDF nao executa um conformador OpenType; tags de caracteristica "
        "nao tem efeito."
    ),
    "variation_axes": substitute(
        "A fonte variavel foi instanciada estaticamente na coordenada pedida antes de "
        "embutir.",
        "instancia estatica",
    ),
    "small_caps": PropertySupport(
        by_value={
            "none": full(),
            "synthetic": full(),
            "real": substitute(
                "O conjunto 'smcp' exige conformacao OpenType; foi desenhado versalete "
                "sintetico com correcao de peso.",
                "versalete sintetico",
            ),
            "petite": substitute(
                "O conjunto 'pcap' exige conformacao OpenType.", "versalete sintetico"
            ),
            "unicase": unsupported("Nao ha forma unicase sem conformacao OpenType."),
        }
    ),
    "numeral_figure": unsupported(
        "Algarismos antigos exigem conformacao OpenType, que este escritor nao executa."
    ),
    "numeral_spacing": unsupported(
        "Algarismos tabulares exigem conformacao OpenType, que este escritor nao executa."
    ),
    "underline": PropertySupport(
        by_value={
            "none": full(),
            "single": full(),
            "double": full(),
            "thick": full(),
            "dotted": full(),
            "dotted-heavy": full(),
            "dashed": full(),
            "dashed-heavy": full(),
            "dash-long": full(),
            "dash-dot": full(),
            "dash-dot-dot": full(),
            "words-only": full(),
            "wavy": approximate("O traco ondulado foi desenhado com arcos aproximados.", "onda"),
            "wavy-double": approximate("O traco ondulado duplo foi aproximado.", "onda dupla"),
            "wavy-heavy": approximate("O traco ondulado grosso foi aproximado.", "onda grossa"),
        }
    ),
    "underline_skip_ink": unsupported(
        "Interromper o traco nos descendentes exigiria medir cada glifo; nao implementado."
    ),
    "shadow": approximate(
        "A sombra foi desenhada como uma copia deslocada do texto; nao ha desfoque.",
        "copia deslocada",
    ),
    "emboss": unsupported("Nao ha relevo de texto no modelo grafico do PDF."),
    "engrave": unsupported("Nao ha baixo-relevo de texto no modelo grafico do PDF."),
    "emphasis_mark": unsupported("Marcas de enfase laterais nao estao implementadas."),
    "direction": unsupported(
        "Este escritor nao implementa o algoritmo bidirecional Unicode; o texto e escrito "
        "na ordem logica."
    ),
    "spell_check": unsupported("O PDF nao carrega marcacao de revisao ortografica."),
    "text_transform": PropertySupport(
        by_value={
            "none": full(),
            "uppercase": full(),
            "lowercase": full(),
            "capitalize": full(),
            "full-width": unsupported("Nao ha transformacao para largura plena."),
        }
    ),
}

_PDF_PARAGRAPH: Mapping[str, PropertySupport] = {
    "mark_props": unsupported(
        "Nao existe marca de paragrafo neste formato; a formatacao do pilcrow "
        "nao tem onde ser gravada."
    ),
    "suppress_line_numbers": unsupported("Este escritor nao numera linhas."),
}

_PDF_FEATURES: Mapping[str, PropertySupport] = {
    "vector_diagram": full(),
    "named_styles": substitute("Resolvidos em formatacao direta.", "formatacao direta"),
    "footnotes": full(),
    "endnotes": full(),
    "auto_numbering": full(),
    "toc_field": substitute(
        "O PDF nao tem campo de sumario; a lista foi composta na exportacao e ligada por "
        "destinos internos.",
        "sumario composto",
    ),
    "columns": full(),
    "page_geometry": full(),
    "headers_footers": full(),
    "drop_cap": full(),
    "math": substitute(
        "A formula foi composta como o proprio LaTeX em fonte monoespacada; nao ha "
        "compositor matematico neste escritor.",
        "texto LaTeX literal",
    ),
    "index_entry": substitute(
        "As entradas viraram destinos nomeados e uma lista remissiva no fim.",
        "destinos + lista remissiva",
    ),
    "interactive_replay": unsupported("Este escritor nao emite JavaScript de PDF."),
    "dark_mode": unsupported("O PDF nao tem tema escuro."),
    "font_embedding": full(),
    "accessibility_tags": full(),
    "raw_passthrough": unsupported(
        "Um bloco RawPassthrough de outro formato nao tem equivalente no PDF."
    ),
    "fixed_layout": full(),
    "pdf_a": full(),
}


PDF_PROFILE = FormatProfile(
    name="pdf",
    run=_PDF_RUN,
    paragraph=_PDF_PARAGRAPH,
    features=_PDF_FEATURES,
    node_fields=_AUDIT_FIELDS,
    vector_diagrams=True,
)


PROFILES: Mapping[str, FormatProfile] = {
    profile.name: profile
    for profile in (DOCX_PROFILE, EPUB_PROFILE, HTML_PROFILE, LATEX_PROFILE, PDF_PROFILE)
}
"""Every declared profile, keyed by format name."""


def profile_for(name: str) -> FormatProfile:
    """Return the capability table of a format.

    Args:
        name: The format name, e.g. ``"epub"``.

    Returns:
        The profile.

    Raises:
        KeyError: No such format.
    """
    return PROFILES[name]
