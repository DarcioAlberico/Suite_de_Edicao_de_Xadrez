# ruff: noqa: E501 - o conteúdo das fixtures (XHTML) vai em linhas longas, como no arquivo gerado
"""Gera tests/fixtures/editor/defeitos/ (H10): um arquivo por regra, com o esperado ao lado.

Roda com o Python da suíte: `python tests/fixtures/editor/defeitos/gerar_defeitos.py [pasta]`
(sem a pasta, escreve ao lado dele; o teste `test_as_fixtures_sao_do_gerador` gera numa pasta
temporária e compara byte a byte).

O local esperado sai de um marcador no próprio texto do arquivo (a definição da regra: o `<` do
elemento, o nome da declaração, o caractere), nunca do validador.
"""
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
import chess

from caissa.core.model import DiagramSource, Provenance, RecognitionResult, SourceKind
from caissa.core.model.diagram import RecognitionPath
from caissa.core.model.ids import ULID
from caissa.editor.leitura import mapa_para_json
from caissa.export.legivel import (
    Duvida,
    MapaDaProveniencia,
    RegistroDoMapa,
    imagem_do_diagrama,
)

PASTA = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
INICIO = chess.STARTING_FEN


def depois(*sans: str) -> str:
    tabuleiro = chess.Board()
    for san in sans:
        tabuleiro.push_san(san)
    return tabuleiro.fen()


def xhtml(corpo: str, cabeca: str = "", *, lang: bool = True, doctype: str = "<!DOCTYPE html>") -> str:
    atributos = ' lang="pt-BR" xml:lang="pt-BR"' if lang else ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n' + doctype + "\n"
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
            f'{atributos}>\n<head>\n<title>Um defeito</title>\n{cabeca}</head>\n<body>\n{corpo}\n'
            "</body>\n</html>\n")


def png(largura: int, altura: int, cor: tuple[int, int, int]) -> bytes:
    linha = b"\x00" + bytes(cor) * largura

    def bloco(tipo: bytes, conteudo: bytes) -> bytes:
        return (struct.pack(">I", len(conteudo)) + tipo + conteudo
                + struct.pack(">I", zlib.crc32(tipo + conteudo) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(linha * altura)) + bloco(b"IEND", b""))


def gif_animado() -> bytes:
    """Um GIF 1×1 com dois quadros e o laço do NETSCAPE2.0."""
    cabeca = b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x80, 0, 0) + b"\x00\x00\x00\xff\xff\xff"
    laco = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    quadro = (b"\x21\xf9\x04\x00\x0a\x00\x00\x00" + b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0)
              + b"\x02\x02\x44\x01\x00")
    return cabeca + laco + quadro + quadro + b"\x3b"


def apng() -> bytes:
    """Um PNG com o bloco `acTL` (dois quadros) antes dos dados: o APNG."""
    normal = png(1, 1, (0, 0, 0))
    actl = b"acTL" + struct.pack(">II", 2, 0)
    bloco = struct.pack(">I", 8) + actl + struct.pack(">I", zlib.crc32(actl) & 0xFFFFFFFF)
    fim_do_ihdr = 8 + 25
    return normal[:fim_do_ihdr] + bloco + normal[fim_do_ihdr:]


def webp_animado() -> bytes:
    """Um WebP com a marca de animação no `VP8X`."""
    vp8x = b"VP8X" + struct.pack("<I", 10) + bytes([0x02, 0, 0, 0]) + bytes(6)
    return b"RIFF" + struct.pack("<I", 4 + len(vp8x)) + b"WEBP" + vp8x


def marcador_de_pagina(ident: str, rotulo: str) -> str:
    return f'<span epub:type="pagebreak" role="doc-pagebreak" id="{ident}" aria-label="{rotulo}"/>'


def lista_de_paginas(entradas: list[tuple[str, str]]) -> str:
    itens = "".join(f'<li><a href="{href}">{rotulo}</a></li>\n' for href, rotulo in entradas)
    return f'<nav epub:type="page-list" role="doc-pagelist" hidden="hidden">\n<ol>\n{itens}</ol>\n</nav>'


def local(texto: str, marcador: str, ocorrencia: int = 1) -> tuple[int, int]:
    """A linha e a coluna (de 1) da `ocorrencia`-ésima vez do marcador no texto."""
    posicao = -1
    for _ in range(ocorrencia):
        posicao = texto.index(marcador, posicao + 1)
    linha = texto.count("\n", 0, posicao) + 1
    coluna = posicao - texto.rfind("\n", 0, posicao)
    return linha, coluna


def diagrama(fen: str, *, ident: str = "p1-d1", stm: str | None = None, src: str | None = None,
             alt: str = "Diagrama de xadrez: jogam as brancas, posição inicial.") -> str:
    lado = stm if stm is not None else fen.split()[1]
    imagem = src if src is not None else f"../Images/{imagem_do_diagrama(fen, 'white')}"
    return (f'<figure class="cb-diagram" id="{ident}" data-fen="{fen}" data-stm="{lado}" '
            f'data-mode="svg" data-orientation="white">\n'
            f'  <img class="cb-svg" src="{imagem}" alt="{alt}"/>\n</figure>')


def lance(san: str, fen: str, texto: str | None = None, extra: str = "") -> str:
    return f'<span class="cb-move" data-san="{san}" data-fen="{fen}"{extra}>{texto or san}</span>'


FIXTURES: dict[str, dict] = {}


def defeito(codigo: str, texto: str, marcadores: list[tuple[str, str, int]] | None = None,
            *, arquivo: str | None = None, contexto: dict | None = None) -> None:
    """Registra o arquivo e o que ele tem de dar: [(código, marcador, ocorrência)]."""
    nome = arquivo or f"Text/{codigo}.xhtml"
    esperados = []
    for regra_, marcador, ocorrencia in marcadores or [(codigo, "", 1)]:
        linha, coluna = local(texto, marcador, ocorrencia)
        esperados.append({"codigo": regra_, "linha": linha, "coluna": coluna})
    FIXTURES[nome] = {"texto": texto, "regra": codigo, "problemas": esperados,
                      "contexto": contexto or {}}


# --- XML e a R4.3 ------------------------------------------------------------------------------
t = xhtml("<p>Um parágrafo que fecha com a etiqueta errada.</span>")
defeito("xml-mal-formado", t, [("xml-mal-formado", "span>", 1)])
aninhado = "\n".join("<div>" for _ in range(300)) + "\n<p>fundo</p>\n" + "\n".join("</div>" for _ in range(300))
t = xhtml(aninhado)
defeito("seg-aninhamento", t, [("seg-aninhamento", "<div>", 255)])
t = xhtml("<p>O autor é &autor;.</p>", doctype='<!DOCTYPE html [\n<!ENTITY autor "Anand">\n]>')
defeito("seg-doctype-entidade", t, [("seg-doctype-entidade", "<!ENTITY", 1)])
t = xhtml("<p>O arquivo: &arquivo;.</p>",
          doctype='<!DOCTYPE html [\n<!ENTITY arquivo SYSTEM "file:///C:/Windows/win.ini">\n]>')
defeito("seg-entidade-externa", t, [("seg-entidade-externa", "<!ENTITY", 1)])

# --- A R4.2 ------------------------------------------------------------------------------------
t = xhtml('<p>Um parágrafo.</p>\n<script>document.title = "outro";</script>')
defeito("seg-script", t, [("seg-script", "<script", 1)])
t = xhtml('<p onclick="alert(1)">Um parágrafo que responde ao clique.</p>')
defeito("seg-evento", t, [("seg-evento", "<p onclick", 1)])
t = xhtml('<p>Veja <a href="javascript:alert(1)">o diagrama 3</a>.</p>')
defeito("seg-javascript", t, [("seg-javascript", '<a href="javascript', 1)])
t = xhtml('<iframe src="outro.xhtml" title="outro capítulo"></iframe>')
defeito("seg-embutido", t, [("seg-embutido", "<iframe", 1)])
t = xhtml('<p><img src="https://exemplo.invalid/diagrama.png" alt="Um diagrama de fora"/></p>')
defeito("seg-recurso-remoto", t, [("seg-recurso-remoto", "<img", 1)])
t = xhtml("<p>Um parágrafo.</p>",
          "<style>@import url(https://exemplo.invalid/tema.css);</style>\n")
defeito("seg-import-remoto", t, [("seg-import-remoto", "@import", 1)])
t = xhtml('<p><img src="../../fora.png" alt="Uma imagem de fora do livro"/></p>')
defeito("seg-caminho-fora", t, [("seg-caminho-fora", "<img", 1)])

# --- O contrato --------------------------------------------------------------------------------
t = xhtml('<figure class="cb-diagram" id="p1-d1" data-stm="w" data-mode="svg">\n'
          '  <img class="cb-svg" src="../Images/dg_000000000000.svg" alt="Diagrama de xadrez."/>\n</figure>')
defeito("contrato-diagrama-sem-fen", t, [("contrato-diagrama-sem-fen", "<figure", 1)])
t = xhtml(diagrama("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq - 0 1",
                   src="../Images/dg_000000000000.svg"))
defeito("contrato-fen-invalida", t, [("contrato-fen-invalida", "<figure", 1)])
t = xhtml(diagrama(INICIO, stm="b"))
defeito("contrato-stm-incoerente", t, [("contrato-stm-incoerente", "<figure", 1)])
t = xhtml(diagrama(INICIO, src="../Images/dg_000000000000.svg"))
defeito("contrato-svg-incoerente", t, [("contrato-svg-incoerente", '<img class="cb-svg"', 1)])
t = xhtml('<p><img src="../Images/nao-existe.png" alt="Uma imagem que falta"/></p>')
defeito("contrato-imagem-ausente", t, [("contrato-imagem-ausente", "<img", 1)])
t = xhtml('<p>Depois de <span class="cb-move" data-san="e4">e4</span> as brancas atacam.</p>')
defeito("contrato-lance-sem-fen", t, [("contrato-lance-sem-fen", '<span class="cb-move"', 1)])
t = xhtml('<p>Veja <span class="nota-cb-move">a nota</span> abaixo.</p>')
defeito("contrato-classe-confundida", t, [("contrato-classe-confundida", "<span", 1)])
t = xhtml('<p class="cb-diagramm">Um parágrafo com a classe errada.</p>')
defeito("contrato-classe-desconhecida", t, [("contrato-classe-desconhecida", '<p class=', 1)])

# --- O xadrez ----------------------------------------------------------------------------------
t = xhtml('<p class="cb-line cb-mainline">' + lance("e4", depois("e4")) + " "
          + lance("Ke3", depois("e4")) + "</p>")
defeito("xadrez-lance-ilegal", t, [("xadrez-lance-ilegal", '<span class="cb-move" data-san="Ke3"', 1)])
t = xhtml('<p class="cb-line cb-mainline">' + lance("e4", depois("e4")) + " "
          + lance("e5", depois("e4")) + "</p>")
defeito("xadrez-fen-divergente", t, [("xadrez-fen-divergente", '<span class="cb-move" data-san="e5"', 1)])
t = xhtml('<p class="cb-line cb-mainline">' + lance("e4", depois("e4")) + "</p>\n" + diagrama(INICIO))
defeito("xadrez-diagrama-diverge", t, [("xadrez-diagrama-diverge", "<figure", 1)])
t = xhtml('<p class="cb-line cb-mainline">' + lance("Nf3", depois("Nf3")) + " "
          + lance("Nf6", depois("Nf3", "Nf6"), texto="Sf6") + "</p>")
defeito("xadrez-notacao-misturada", t, [("xadrez-notacao-misturada", '<span class="cb-move" data-san="Nf6"', 1)])
t = xhtml("<p>O lance " + lance("Nf3", depois("Nf3"), texto='<span class="cb-piece" data-piece="N">♘</span>f3')
          + " desenvolve o cavalo.</p>",
          '<link rel="stylesheet" type="text/css" href="../Styles/fonte.css"/>\n')
defeito("xadrez-figurina-fora-da-fonte", t, [("xadrez-figurina-fora-da-fonte", "♘", 1)],
        contexto={"fontes": {"Times": "tiro"}})

# --- O CSS -------------------------------------------------------------------------------------
t = xhtml("<p>Um parágrafo.</p>", "<style>p { color red; }</style>\n")
# O erro de sintaxe aponta onde o tinycss2 o achou: o token que veio no lugar do ":".
defeito("css-sintaxe", t, [("css-sintaxe", "red;", 1)])
t = xhtml('<p class="aviso">Um parágrafo.</p>', "<style>p.aviso { colour: #000; }</style>\n")
defeito("css-propriedade-desconhecida", t, [("css-propriedade-desconhecida", "colour", 1)])
t = xhtml('<p class="canto">Um parágrafo.</p>', "<style>p.canto { border-radius: 4px; }</style>\n")
defeito("css-motor-nao-desenha", t, [("css-motor-nao-desenha", "border-radius", 1)])
t = "div.nota { color: #222222; }\n"
defeito("css-mapa-docx", t, [("css-mapa-docx", "div.nota", 1)], arquivo="Styles/css-mapa-docx.css")
t = xhtml('<p class="cinza">Um parágrafo em cinza, a 5,7 para 1 sobre o papel branco.</p>',
          '<link rel="stylesheet" type="text/css" href="../Styles/cinza.css"/>\n')
defeito("css-contraste", t, [("css-contraste", '<p class="cinza"', 1)])
# O contraste com qualquer CSS (o ciclo 1 do crítico do H10): a variável do <style> e o texto
# repetido (acusa o segundo, e não o primeiro igual); a variável de uma classe e a do style=""
# herdadas; o fundo que cobre parte do trecho e o translúcido; o papel do body; a imagem sob o
# texto; e a página que não termina.
t = xhtml('<p>O mesmo texto.</p>\n<p class="nota">O mesmo texto.</p>',
          "<style>:root { --cinza: #767676; }\np.nota { color: var(--cinza); }</style>\n")
defeito("css-contraste", t, [("css-contraste", '<p class="nota"', 1)],
        arquivo="Text/css-contraste-variavel.xhtml")
t = xhtml('<div class="aviso">\n<p>Dentro do aviso.</p>\n</div>\n<p>Fora do aviso.</p>\n'
          '<div style="--tinta: #888888">\n<p>No estilo do pai.</p>\n</div>',
          "<style>.aviso { --tinta: #808080; }\np { color: var(--tinta, #000000); }</style>\n")
defeito("css-contraste", t, [("css-contraste", "<p>Dentro", 1), ("css-contraste", "<p>No estilo", 1),
                             ("css-motor-nao-desenha", "color: var", 1)],
        arquivo="Text/css-contraste-heranca.xhtml")
t = xhtml('<p>Um texto com <span style="background-color: #777777">um fundo cinza</span> no meio.</p>\n'
          '<p style="background-color: rgba(0, 0, 0, 0.6); color: #ffffff">Branco no translúcido.</p>')
defeito("css-contraste", t, [("css-contraste", '<span style="background', 1),
                             ("css-contraste", '<p style="background', 1),
                             ("css-motor-nao-desenha", '<p style="background', 1)],
        arquivo="Text/css-contraste-fundo.xhtml")
t = xhtml("<p>Cinza no papel escuro.</p>",
          "<style>body { background-color: #000000; color: #555555; }</style>\n")
defeito("css-contraste", t, [("css-contraste", "<p>Cinza", 1)], arquivo="Text/css-contraste-papel.xhtml")
# O link que o autor pinta de cinza: o MuPDF sozinho o pintaria do azul dele (e passaria).
t = xhtml('<p>Veja <a href="#fim">o fim do capítulo</a>.</p>\n<p id="fim">O fim.</p>',
          "<style>a { color: #999999; }</style>\n")
defeito("css-contraste", t, [("css-contraste", '<a href="#fim"', 1)], arquivo="Text/css-contraste-link.xhtml")
t = xhtml('<div style="position: relative">\n<img src="../Images/escura.png" alt="Um fundo escuro"/>\n'
          '<p style="position: absolute; top: 0; color: #333333">Sobre a imagem.</p>\n</div>')
defeito("css-contraste", t, [("css-contraste", '<p style="position', 1)],
        arquivo="Text/css-contraste-imagem.xhtml")
t = xhtml("\n".join(f"<p>A linha {n} de um capítulo mais alto que a página medida.</p>"
                    for n in range(1, 501)))
defeito("css-contraste-incompleto", t, [("css-contraste-incompleto", "<body", 1)],
        contexto={"teto_de_paginas": 1})

# --- A acessibilidade --------------------------------------------------------------------------
t = xhtml("<p>Um livro sem a língua dita.</p>", lang=False)
defeito("a11y-lang", t, [("a11y-lang", "<html", 1)])
t = xhtml("<h1>O capítulo</h1>\n<h3>A seção</h3>\n<p>Texto.</p>")
defeito("a11y-titulo-salto", t, [("a11y-titulo-salto", "<h3", 1)])
t = xhtml('<p><img src="../Images/imagem.png"/></p>')
defeito("a11y-alt-ausente", t, [("a11y-alt-ausente", "<img", 1)])
t = xhtml(diagrama(INICIO, alt="Diagrama de xadrez: jogam as brancas; brancas: Rei em e1, Dama em d1."))
defeito("a11y-alt-afirma", t, [("a11y-alt-afirma", '<img class="cb-svg"', 1)],
        contexto={"mapa": "Text/a11y-alt-afirma.proveniencia.json"})
# A mesma página impressa duas vezes, com `id` diferentes: o número é que conta.
t = xhtml(f"<p>{marcador_de_pagina('pg5', '5')}Um parágrafo.</p>\n"
          f"<p>{marcador_de_pagina('pg5b', '5')}Outro parágrafo.</p>")
defeito("a11y-pagina-duplicada", t, [("a11y-pagina-duplicada", "<span epub", 2)])
t = xhtml('<p><span epub:type="pagebreak" role="doc-pagebreak" id="pg5" aria-label="5"/>Um parágrafo.</p>\n'
          '<p><span epub:type="pagebreak" role="doc-pagebreak" id="pg7" aria-label="7"/>Outro.</p>')
defeito("a11y-pagina-lacuna", t, [("a11y-pagina-lacuna", '<span epub:type="pagebreak" role="doc-pagebreak" id="pg7"', 1)])
# A page-list do nav (§5.6): a entrada que aponta para o nada, a que pula, a repetida; e, com o
# nav do livro no contexto, o marcador que ela não lista. As entradas apontam para os marcadores
# do `Text/apoio-paginas.xhtml` (páginas 1 a 4).
t = xhtml(lista_de_paginas([("apoio-paginas.xhtml#pg1", "1"), ("apoio-paginas.xhtml#pg2", "2"),
                            ("apoio-paginas.xhtml#pg9", "3")]))
defeito("a11y-pagina-sem-alvo", t, [("a11y-pagina-sem-alvo", '<a href="apoio-paginas.xhtml#pg9"', 1)])
t = xhtml(lista_de_paginas([("apoio-paginas.xhtml#pg1", "1"), ("apoio-paginas.xhtml#pg2", "2"),
                            ("apoio-paginas.xhtml#pg4", "4")]))
defeito("a11y-pagina-lacuna", t, [("a11y-pagina-lacuna", '<a href="apoio-paginas.xhtml#pg4"', 1)],
        arquivo="Text/a11y-pagina-lacuna-lista.xhtml")
t = xhtml(lista_de_paginas([("apoio-paginas.xhtml#pg1", "1"), ("apoio-paginas.xhtml#pg2", "2"),
                            ("apoio-paginas.xhtml#pg2", "2")]))
defeito("a11y-pagina-duplicada", t, [("a11y-pagina-duplicada", '<a href="apoio-paginas.xhtml#pg2"', 2)],
        arquivo="Text/a11y-pagina-duplicada-lista.xhtml")
t = xhtml(f"<p>{marcador_de_pagina('pg7', '7')}Uma página que o nav do livro não lista.</p>")
defeito("a11y-pagina-fora-da-lista", t, [("a11y-pagina-fora-da-lista", "<span epub", 1)],
        contexto={"nav": "Text/a11y-pagina-sem-alvo.xhtml"})
t = xhtml('<p><img class="cb-imagem-de-texto" src="../Images/texto.png" '
          'alt="Trecho da página 12, mantido como imagem"/></p>')
defeito("a11y-imagem-de-texto", t, [("a11y-imagem-de-texto", "<img", 1)])
t = xhtml('<video src="../Images/filme.mp4"></video>')
defeito("a11y-midia", t, [("a11y-midia", "<video", 1)])
t = xhtml("<p><button>Mostrar a solução</button></p>")
defeito("a11y-interativo", t, [("a11y-interativo", "<button", 1)])
t = xhtml("<p>Um parágrafo.</p>", '<meta http-equiv="refresh" content="30"/>\n')
defeito("a11y-refresh", t, [("a11y-refresh", "<meta", 1)])
t = xhtml('<p class="pisca">Um parágrafo.</p>', "<style>p.pisca { transition: color 1s; }</style>\n")
defeito("a11y-animacao", t, [("a11y-animacao", "transition", 1)])
t = xhtml('<p><img src="../Images/animada.gif" alt="Uma animação"/></p>')
defeito("a11y-animacao", t, [("a11y-animacao", "<img", 1)], arquivo="Text/a11y-animacao-gif.xhtml")
# A imagem animada em toda fonte (o ciclo 1 do crítico): o srcset, a <source> da <picture>, o
# WebP, e o url() da folha.
t = xhtml('<p><img src="../Images/imagem.png" srcset="../Images/animada.gif 2x" alt="Uma imagem"/></p>')
defeito("a11y-animacao", t, [("a11y-animacao", "<img", 1)], arquivo="Text/a11y-animacao-srcset.xhtml")
t = xhtml('<picture>\n<source srcset="../Images/animada.png" type="image/apng"/>\n'
          '<img src="../Images/imagem.png" alt="Uma imagem"/>\n</picture>')
defeito("a11y-animacao", t, [("a11y-animacao", "<source", 1)], arquivo="Text/a11y-animacao-picture.xhtml")
t = xhtml('<p><img src="../Images/animada.webp" alt="Uma animação"/></p>')
defeito("a11y-animacao", t, [("a11y-animacao", "<img", 1)], arquivo="Text/a11y-animacao-webp.xhtml")
t = xhtml('<p class="fundo">Um parágrafo.</p>',
          "<style>p.fundo { background-image: url(../Images/animada.gif); }</style>\n")
defeito("a11y-animacao", t, [("a11y-animacao", "background-image", 1),
                             ("css-motor-nao-desenha", "background-image", 1)],
        arquivo="Text/a11y-animacao-css.xhtml")
t = xhtml('<p class="barra">Um parágrafo.</p>', "<style>p.barra { position: fixed; }</style>\n")
defeito("a11y-fixo", t, [("a11y-fixo", "position", 1)])
t = xhtml('<p><a href="#fim">ir ao fim</a></p>\n<p id="fim">O fim.</p>',
          "<style>a:focus { outline: none; }</style>\n")
defeito("a11y-foco-apagado", t, [("a11y-foco-apagado", "outline", 1)])
t = xhtml('<p id="ref1">Texto da nota. <a href="#ref1">↩</a></p>')
defeito("a11y-link-proposito", t, [("a11y-link-proposito", '<a href="#ref1"', 1)])
t = xhtml("<section>\n<h1>O capítulo</h1>\n<p>Texto.</p>\n</section>")
defeito("a11y-regiao-sem-papel", t, [("a11y-regiao-sem-papel", "<section", 1)])
t = xhtml("<p>O lance " + lance("e4", depois("e4"), texto='e4<span class="cb-nag" data-nag="5">!?</span>')
          + " é interessante.</p>")
defeito("a11y-simbolo-fora-do-glossario", t, [("a11y-simbolo-fora-do-glossario", '<span class="cb-nag"', 1)],
        contexto={"glossario": ["!"]})
t = xhtml("<p>O GM Carlsen venceu a partida.</p>")
defeito("a11y-abreviatura", t, [("a11y-abreviatura", "GM", 1)])
t = xhtml('<p data-confidence="0.87">Um texto lido pelo OCR.</p>')
defeito("a11y-proveniencia", t, [("a11y-proveniencia", "<p data-confidence", 1)])

# --- O OCR -------------------------------------------------------------------------------------
t = xhtml('<p id="p1-1">Um trecho duvidoso no meio.</p>')
defeito("ocr-duvida-pendente", t, [("ocr-duvida-pendente", '<p id="p1-1"', 1)],
        contexto={"mapa": "Text/ocr-duvida-pendente.proveniencia.json"})

# --- Os arquivos de apoio ----------------------------------------------------------------------
for sub in ("Text", "Styles", "Images"):
    (PASTA / sub).mkdir(parents=True, exist_ok=True)
for nome, dados in FIXTURES.items():
    (PASTA / nome).write_text(dados["texto"], encoding="utf-8", newline="\n")
(PASTA / "Styles" / "cinza.css").write_text("p.cinza { color: #666666; }\n", encoding="utf-8",
                                            newline="\n")
(PASTA / "Styles" / "fonte.css").write_text(".cb-piece { font-family: Times, serif; }\n",
                                            encoding="utf-8", newline="\n")
(PASTA / "Images" / "imagem.png").write_bytes(png(4, 4, (40, 120, 200)))
(PASTA / "Images" / "texto.png").write_bytes(png(4, 4, (30, 30, 30)))
(PASTA / "Images" / "animada.gif").write_bytes(gif_animado())
(PASTA / "Images" / "animada.png").write_bytes(apng())
(PASTA / "Images" / "animada.webp").write_bytes(webp_animado())
(PASTA / "Images" / "escura.png").write_bytes(png(40, 30, (20, 20, 20)))
(PASTA / "Text" / "apoio-paginas.xhtml").write_text(xhtml("\n".join(
    f"<p>{marcador_de_pagina(f'pg{n}', str(n))}A página {n}.</p>" for n in range(1, 5))),
    encoding="utf-8", newline="\n")
svg = ('<?xml version="1.0" encoding="utf-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="8" '
       'height="8"><rect width="8" height="8" fill="#ccc"/></svg>\n')
for nome in ("dg_000000000000.svg", imagem_do_diagrama(INICIO, "white")):
    (PASTA / "Images" / nome).write_text(svg, encoding="utf-8", newline="\n")
(PASTA / "Images" / "filme.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")

ocr = Provenance(kind=SourceKind.OCR, page_index=0, confidence=0.5)
mapa_do_alt = MapaDaProveniencia(nos={"p1-d1": RegistroDoMapa(
    ir_id=ULID.from_int(1), origem="pagina", proveniencia=None,
    fonte=DiagramSource(kind=SourceKind.VISION, page_index=0),
    reconhecimento=RecognitionResult(fen=INICIO, overall_confidence=0.8,
                                     path=RecognitionPath.NEURAL),
    conferido=False)})
mapa_da_duvida = MapaDaProveniencia(nos={"p1-1": RegistroDoMapa(
    ir_id=ULID.from_int(2), origem="pagina", proveniencia=ocr,
    duvidas=(Duvida(ini=9, fim=18, proveniencia=ocr),))})
for nome, mapa in (("a11y-alt-afirma", mapa_do_alt), ("ocr-duvida-pendente", mapa_da_duvida)):
    (PASTA / "Text" / f"{nome}.proveniencia.json").write_text(
        json.dumps(mapa_para_json(mapa), ensure_ascii=False, indent=1), encoding="utf-8",
        newline="\n")

esperado = {
    "leia-me": ("Um arquivo por regra do validador (H10). O local esperado sai de um marcador no "
                "texto do arquivo (o < do elemento, o nome da declaração, o caractere), pela "
                "definição da regra; o portão exige exatamente estes problemas em cada arquivo."),
    "defeitos": {nome: {k: v for k, v in dados.items() if k != "texto"}
                 for nome, dados in sorted(FIXTURES.items())},
    "gerados": {"seg-tamanho": {"regra": "seg-tamanho", "problemas": [
        {"codigo": "seg-tamanho", "linha": 1, "coluna": 1}],
        "como": "um XHTML de 8 MB e 1 byte, montado pelo portão"}},
}
(PASTA / "esperado.json").write_text(json.dumps(esperado, ensure_ascii=False, indent=1),
                                     encoding="utf-8", newline="\n")
(PASTA / "LEIAME.md").write_text(
    "# Os defeitos do validador (Editor HTML/CSS, H10)\n\n"
    "Um arquivo por regra (`Text/<código>.xhtml`, e o `Styles/css-mapa-docx.css`), cada um com o\n"
    "defeito da regra e nenhum outro — e, para as regras que o crítico pediu mais (o contraste com\n"
    "qualquer CSS, a imagem animada em toda fonte, a page-list), um arquivo por caso\n"
    "(`Text/<código>-<caso>.xhtml`); `esperado.json` diz o código e a linha:coluna que o\n"
    "validador tem de dar — tirados de um marcador no texto (o `<` do elemento, o nome da\n"
    "declaração, o caractere), pela definição da regra, e não do validador. Os de apoio: as\n"
    "imagens (`Images/`), as folhas ligadas (`Styles/cinza.css`, `Styles/fonte.css`), os mapas\n"
    "da proveniência (`Text/*.proveniencia.json`) e os marcadores de página que as page-list\n"
    "apontam (`Text/apoio-paginas.xhtml`). O `seg-tamanho` (8 MB) o portão monta.\n"
    "Regerar: `python tests/fixtures/editor/defeitos/gerar_defeitos.py` — o mesmo resultado, byte\n"
    "a byte (os `ir_id` dos mapas são fixos); o teste `test_as_fixtures_sao_do_gerador` confere.\n",
    encoding="utf-8", newline="\n")
print(len(FIXTURES), "arquivos de defeito;", len({d['regra'] for d in FIXTURES.values()}) + 1, "regras")
