# ruff: noqa: E501 - o conteúdo das fixtures (XHTML) vai em linhas longas, como no arquivo gerado
"""Gera tests/fixtures/editor/hostil/ (o livro hostil do H1): uma página por vetor.

Com {PORTA} (o servidor em 127.0.0.1 do `editor_motores.py --hostil`) e {FORA} (a sentinela).
Roda com o Python da suíte: `python tests/fixtures/editor/hostil/gerar_hostil.py`.
"""
import struct
import zlib
from pathlib import Path

PASTA = Path(__file__).resolve().parent
MARCA = "document.documentElement.setAttribute('data-hostil', '{}')"


def pagina(titulo: str, corpo: str, cabeca: str = "") -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            'lang="pt-BR" xml:lang="pt-BR">\n<head>\n'
            f'<title>{titulo}</title>\n{cabeca}'
            '<link rel="stylesheet" type="text/css" href="../Styles/livro.css"/>\n</head>\n'
            f'<body>\n<h1>{titulo}</h1>\n{corpo}\n</body>\n</html>\n')


def png(largura: int, altura: int, cor: tuple[int, int, int]) -> bytes:
    linha = b"\x00" + bytes(cor) * largura
    dados = zlib.compress(linha * altura)

    def bloco(tipo: bytes, conteudo: bytes) -> bytes:
        return (struct.pack(">I", len(conteudo)) + tipo + conteudo
                + struct.pack(">I", zlib.crc32(tipo + conteudo) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0))
            + bloco(b"IDAT", dados) + bloco(b"IEND", b""))


PAGINAS = {
    "01_script.xhtml": pagina("Script no livro", (
        "<p>Um parágrafo antes do script.</p>\n"
        f"<script>{MARCA.format('script')}; new Image().src = 'http://127.0.0.1:{{PORTA}}/script';"
        "</script>\n<p>Um parágrafo depois.</p>")),
    "02_onerror.xhtml": pagina("Manipulador de evento", (
        '<p>A imagem que falta dispara o <code>onerror</code>.</p>\n'
        f'<p><img src="../Images/nao_existe.png" alt="falta" onerror="{MARCA.format("onerror")}"/></p>')),
    "03_javascript_url.xhtml": pagina("Link javascript:", (
        f'<p><a id="j" href="javascript:{MARCA.format("javascript-url")}">o link que roda '
        'código</a></p>')),
    "04_imagens_externas.xhtml": pagina("Imagens de fora", (
        '<p><img src="http://127.0.0.1:{PORTA}/imagem.png" alt="por http"/></p>\n'
        '<p><img src="https://127.0.0.1:{PORTA}/imagem-tls.png" alt="por https"/></p>')),
    "05_css_externo.xhtml": pagina("CSS de fora", (
        '<p class="fonte-externa">O texto com a fonte e o fundo de fora.</p>'),
        '<link rel="stylesheet" type="text/css" href="../Styles/hostil.css"/>\n'),
    "06_iframe.xhtml": pagina("Iframe", (
        '<iframe src="http://127.0.0.1:{PORTA}/iframe.html" title="de fora"></iframe>')),
    "07_refresh.xhtml": pagina("Meta refresh", "<p>A página que tenta ir embora.</p>",
                              '<meta http-equiv="refresh" content="0;url=http://127.0.0.1:{PORTA}/refresh"/>\n'),
    "08_svg_script.xhtml": pagina("SVG com script", (
        '<p><svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
        f'<script>{MARCA.format("svg-inline")}</script>'
        '<rect width="40" height="20" fill="#ccc"/></svg></p>\n'
        '<p><img src="../Images/com_script.svg" alt="svg por img"/></p>\n'
        '<p><object data="../Images/com_script.svg" type="image/svg+xml">svg por object</object></p>')),
    "09_arquivos_fora.xhtml": pagina("Arquivos fora do livro", (
        '<p><img src="C:/Windows/win.ini" alt="caminho do Windows"/></p>\n'
        '<p><img src="file:///C:/Windows/win.ini" alt="file do Windows"/></p>\n'
        '<p><img src="../../fora.png" alt="subindo pastas"/></p>\n'
        '<p><img src="{FORA}" alt="a sentinela fora do livro"/></p>\n'
        '<p><img src="../Images/dentro.png" alt="a imagem de dentro"/></p>')),
}
SVG = ('<?xml version="1.0" encoding="utf-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="40" '
       'height="20" viewBox="0 0 40 20">\n'
       "<script>document.documentElement.setAttribute('data-hostil', 'svg-arquivo'); "
       "new Image().src = 'http://127.0.0.1:{PORTA}/svg-arquivo';</script>\n"
       '<rect width="40" height="20" fill="#9c9"/>\n</svg>\n')
CSS_HOSTIL = ("@import url(http://127.0.0.1:{PORTA}/import.css);\n"
              "@font-face { font-family: \"Externa\"; src: url(http://127.0.0.1:{PORTA}/fonte.woff); }\n"
              "body { background-image: url(http://127.0.0.1:{PORTA}/fundo.png); }\n"
              ".fonte-externa { font-family: \"Externa\", serif; }\n")
CSS_LIVRO = "body { margin: 8px; font-family: serif; }\nimg { width: 40px; height: 40px; }\n"

for sub in ("Text", "Styles", "Images"):
    (PASTA / sub).mkdir(parents=True, exist_ok=True)
for nome, texto in PAGINAS.items():
    (PASTA / "Text" / nome).write_text(texto, encoding="utf-8", newline="\n")
(PASTA / "Styles" / "livro.css").write_text(CSS_LIVRO, encoding="utf-8", newline="\n")
(PASTA / "Styles" / "hostil.css").write_text(CSS_HOSTIL, encoding="utf-8", newline="\n")
(PASTA / "Images" / "com_script.svg").write_text(SVG, encoding="utf-8", newline="\n")
(PASTA / "Images" / "dentro.png").write_bytes(png(8, 8, (40, 120, 200)))
(PASTA / "LEIAME.md").write_text(
    "# O livro hostil (Editor HTML/CSS, H1, tarefa 4)\n\n"
    "Uma página por vetor: o script, o manipulador de evento, o link `javascript:`, as imagens de fora\n"
    "(http e https), o CSS de fora (`@import`, `url()` e `@font-face`), o iframe, o meta refresh, o SVG\n"
    "com script (no texto, por `<img>` e por `<object>`) e os arquivos fora do livro (o caminho do\n"
    "Windows, `file:`, `../../` até a sentinela e o `file:` dela). Todo endereço de fora é `127.0.0.1:{PORTA}`, o\n"
    "servidor que o `benchmarks/editor_motores.py --hostil` abre só para contar o que chega nele: nada\n"
    "sai da máquina. `{FORA}` é o `file:` da sentinela, um PNG fora da pasta do livro. Os scripts marcam\n"
    "`data-hostil` na raiz do documento; o portão exige 0 marcas, 0 requisições e 0 arquivos de fora\n"
    "nos dois motores.\n", encoding="utf-8", newline="\n")
print("ok", sorted(p.name for p in (PASTA / "Text").iterdir()))
