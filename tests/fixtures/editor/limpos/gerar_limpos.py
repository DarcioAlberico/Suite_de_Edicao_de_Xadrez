# ruff: noqa: E501 - o conteúdo das fixtures (XHTML) vai em linhas longas, como no arquivo gerado
"""Gera tests/fixtures/editor/limpos/ (H10): o limpo adversarial, que não pode acusar nada.

Roda com o Python da suíte: `python tests/fixtures/editor/limpos/gerar_limpos.py [pasta]`.

Cada arquivo tem o que está perto de um defeito sem ser um (o ciclo 1 do crítico do H10): o
branco na caixa escura (a caixa do trecho passa da linha), o papel escuro do `body` com o texto
claro, o realce claro que cobre parte do trecho, o fundo translúcido claro, o texto com alfa
quase preto, o sublinhado e o riscado da cor do texto, o texto repetido, o marcador da lista, o
branco sobre a imagem escura; a imagem estática no `src`, no `srcset`, na `<source>` e no
`url()` (o GIF de um quadro, com o laço do NETSCAPE); e as páginas i, ii, 1, 2, 3 com a
`page-list` do `nav` inteira. O portão (`editor_validacao.py`, o limpo) exige 0 problema que
bloqueia ou avisa em todos.
"""
import struct
import sys
import zlib
from pathlib import Path

PASTA = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent


def xhtml(corpo: str, cabeca: str = "") -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
            ' lang="pt-BR" xml:lang="pt-BR">\n<head>\n<title>Um limpo</title>\n'
            f"{cabeca}</head>\n<body>\n{corpo}\n</body>\n</html>\n")


def png(largura: int, altura: int, cor: tuple[int, int, int]) -> bytes:
    linha = b"\x00" + bytes(cor) * largura

    def bloco(tipo: bytes, conteudo: bytes) -> bytes:
        return (struct.pack(">I", len(conteudo)) + tipo + conteudo
                + struct.pack(">I", zlib.crc32(tipo + conteudo) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(linha * altura)) + bloco(b"IEND", b""))


def gif_estatico() -> bytes:
    """Um GIF 1×1 de um quadro só, com o laço do NETSCAPE2.0: estático, apesar do laço."""
    cabeca = b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x80, 0, 0) + b"\x00\x00\x00\xff\xff\xff"
    laco = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    quadro = (b"\x21\xf9\x04\x00\x0a\x00\x00\x00" + b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0)
              + b"\x02\x02\x44\x01\x00")
    return cabeca + laco + quadro + b"\x3b"


def marcador(ident: str, rotulo: str) -> str:
    return f'<span epub:type="pagebreak" role="doc-pagebreak" id="{ident}" aria-label="{rotulo}"/>'


PAGINAS = [("pgi", "i"), ("pgii", "ii"), ("pg1", "1"), ("pg2", "2"), ("pg3", "3")]
ARQUIVOS = {
    "Text/contraste.xhtml": xhtml(
        "<h1>O capítulo</h1>\n"
        "<p>O mesmo texto.</p>\n<p>O mesmo texto.</p>\n"
        '<div class="caixa-escura">\n<p>Branco na caixa escura, com a caixa do trecho passando da linha.</p>\n</div>\n'
        '<p>Um texto com <span class="realce">um realce claro</span> no meio.</p>\n'
        '<p class="translucido">Preto no fundo amarelo translúcido.</p>\n'
        '<p class="alfa">Quase preto, com alfa.</p>\n'
        '<p><u>Sublinhado</u>, <s>riscado</s> e <a href="#fim">um link para o fim</a>.</p>\n'
        "<ul>\n<li>Um item.</li>\n<li>Outro item.</li>\n</ul>\n"
        '<div style="position: relative">\n<img src="../Images/escura.png" alt="Um fundo escuro"/>\n'
        '<p style="position: absolute; top: 0; color: #ffffff">Branco sobre a imagem escura.</p>\n</div>\n'
        '<p id="fim">O fim.</p>',
        "<style>\n:root { --tinta: #1a1a1a; }\nbody { color: var(--tinta); }\n"
        ".caixa-escura { background-color: #222222; color: #ffffff; }\n"
        ".realce { background-color: #fff3b0; }\n"
        ".translucido { background-color: rgba(255, 255, 0, 0.3); }\n"
        ".alfa { color: rgba(0, 0, 0, 0.9); }\n"
        "h1 { page-break-before: always; }\n</style>\n"),
    "Text/escuro.xhtml": xhtml(
        '<p>Claro no papel escuro, com <a href="#fim">um link claro</a>.</p>\n<p id="fim">O fim.</p>',
        "<style>body { background-color: #111111; color: #eeeeee; }\na { color: #9ecbff; }</style>\n"),
    "Text/imagens.xhtml": xhtml(
        '<p><img src="../Images/estatica.gif" alt="Uma imagem estática"/></p>\n'
        '<p><img src="../Images/clara.png" srcset="../Images/clara.png 1x, ../Images/estatica.gif 2x" alt="Uma imagem clara"/></p>\n'
        '<picture>\n<source srcset="../Images/clara.png" type="image/png"/>\n'
        '<img src="../Images/clara.png" alt="Outra imagem clara"/>\n</picture>\n'
        '<p class="fundo">Um fundo de imagem estática.</p>',
        "<style>p.fundo { background-image: url(../Images/estatica.gif); }</style>\n"),
    "Text/paginas.xhtml": xhtml("\n".join(
        f"<p>{marcador(ident, rotulo)}A página {rotulo}.</p>" for ident, rotulo in PAGINAS)),
    "Text/nav.xhtml": xhtml(
        '<nav epub:type="toc" role="doc-toc">\n<ol>\n<li><a href="paginas.xhtml">As páginas</a></li>\n</ol>\n</nav>\n'
        '<nav epub:type="page-list" role="doc-pagelist" hidden="hidden">\n<ol>\n'
        + "".join(f'<li><a href="paginas.xhtml#{ident}">{rotulo}</a></li>\n' for ident, rotulo in PAGINAS)
        + "</ol>\n</nav>"),
}
for sub in ("Text", "Images"):
    (PASTA / sub).mkdir(parents=True, exist_ok=True)
for nome, texto in ARQUIVOS.items():
    (PASTA / nome).write_text(texto, encoding="utf-8", newline="\n")
(PASTA / "Images" / "estatica.gif").write_bytes(gif_estatico())
(PASTA / "Images" / "clara.png").write_bytes(png(8, 8, (230, 230, 230)))
(PASTA / "Images" / "escura.png").write_bytes(png(400, 40, (20, 20, 20)))  # o texto cabe nela
(PASTA / "LEIAME.md").write_text(
    "# O limpo adversarial do validador (Editor HTML/CSS, H10)\n\n"
    "O que está perto de um defeito sem ser um (o contraste no escuro, no realce, no translúcido e\n"
    "sobre a imagem; a imagem estática em toda fonte; a page-list inteira): o portão exige 0\n"
    "problema que bloqueia ou avisa em todo arquivo, com o `Text/nav.xhtml` como o nav do livro.\n"
    "Regerar: `python tests/fixtures/editor/limpos/gerar_limpos.py` (o mesmo resultado, byte a\n"
    "byte).\n", encoding="utf-8", newline="\n")
print(len(ARQUIVOS), "arquivos limpos")
