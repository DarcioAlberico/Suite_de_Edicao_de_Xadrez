"""A camada de segurança (spec S10; R4.2 e R4.3): o que a exportação recusa, e onde.

**R4.2** — a exportação recusa com problema bloqueante, e **não descarta**: `<script>` (no
XHTML e no SVG), atributo `on…`, endereço `javascript:`, `<iframe>`/`<object>`/`<embed>`, recurso
remoto em atributo de recurso (a imagem, a folha, a fonte, o vídeo) e `@import` remoto. Um
`<a href="https://…">` de texto é permitido: um link não é um recurso.

**R4.3** — o caminho de recurso fica contido no projeto: sem subir além da raiz do livro, sem
caminho absoluto (`/x`, `C:/x`, `file:`), sem link simbólico para fora. (O tamanho, o aninhamento
e as entidades são da leitura: `xml.ler`.)

As folhas contam também: a do projeto, o `<style>` e o `style=""` (o `@import`, o `url()` da
fonte e do fundo).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from caissa.editor.validacao.contexto import Contexto, resolver
from caissa.editor.validacao.folha import Folha, folhas_do_documento, nos_de, urls
from caissa.editor.validacao.problema import Problema, Severidade, regra
from caissa.editor.validacao.xml import XLINK_HREF, Documento, Elemento

__all__ = ["verificar", "verificar_folha"]

SCRIPT = regra("seg-script", "segurança", Severidade.BLOQUEIA, "Script no livro (R4.2)",
               "Tire o <script>: o livro não executa nada, e a exportação o recusa.")
EVENTO = regra("seg-evento", "segurança", Severidade.BLOQUEIA,
               "Atributo de evento, on… (R4.2)",
               "Tire o atributo: o livro não executa nada.")
JAVASCRIPT = regra("seg-javascript", "segurança", Severidade.BLOQUEIA,
                   "Endereço javascript: (R4.2)",
                   "Troque o endereço por um destino dentro do livro, ou tire o link.")
EMBUTIDO = regra("seg-embutido", "segurança", Severidade.BLOQUEIA,
                 "Conteúdo embutido: <iframe>, <object> ou <embed> (R4.2)",
                 "Tire o elemento; uma imagem vai num <img> com o arquivo dentro do livro.")
REMOTO = regra("seg-recurso-remoto", "segurança", Severidade.BLOQUEIA,
               "Recurso de fora da máquina (R4.2)",
               "Traga o arquivo para dentro do projeto e aponte para ele pelo caminho relativo.")
IMPORT = regra("seg-import-remoto", "segurança", Severidade.BLOQUEIA,
               "@import de fora da máquina (R4.2)",
               "Traga a folha para dentro do projeto e ligue-a pelo <link>.")
FORA = regra("seg-caminho-fora", "segurança", Severidade.BLOQUEIA,
             "Caminho de recurso fora do projeto (R4.3)",
             "Aponte para um arquivo dentro do livro, por caminho relativo e sem subir além "
             "da raiz.")

_ESQUEMA = re.compile(r"^\s*([a-zA-Z][\w+.-]*):")
_REMOTOS = frozenset({"http", "https", "ftp", "ftps", "ws", "wss", "sftp"})
EMBUTIDOS = frozenset({"iframe", "object", "embed", "frame", "frameset", "applet"})
RECURSOS: dict[str, tuple[str, ...]] = {
    "img": ("src", "srcset"), "source": ("src", "srcset"), "audio": ("src",),
    "video": ("src", "poster"), "track": ("src",), "input": ("src",), "embed": ("src",),
    "object": ("data",), "iframe": ("src",), "frame": ("src",), "script": ("src",),
    "link": ("href",), "image": ("href", XLINK_HREF), "use": ("href", XLINK_HREF),
    "feImage": ("href", XLINK_HREF),
}
"""Os atributos que carregam um recurso, por elemento (o link `<a>` não carrega recurso)."""
ENDERECOS = frozenset({"href", "src", "srcset", "action", "formaction", "data", "poster",
                       "cite", "longdesc", "background", "usemap", XLINK_HREF})


def _enderecos(atributo: str, valor: str) -> list[str]:
    if atributo == "srcset":
        return [parte.strip().split()[0] for parte in valor.split(",") if parte.strip()]
    return [valor]


def classificar(arquivo: str, endereco: str,  # noqa: PLR0911 - um retorno por tipo
                contexto: Contexto) -> str | None:
    """`remoto`, `javascript`, `fora` (absoluto, acima da raiz ou link para fora) ou `None`."""
    esquema = _ESQUEMA.match(endereco)
    if esquema is not None:
        nome = esquema.group(1).lower()
        if nome == "javascript":
            return "javascript"
        if nome in _REMOTOS:
            return "remoto"
        if nome == "data":
            return None
        return "fora"  # file:, c:, e todo esquema que não é do livro
    limpo = endereco.strip()
    if limpo.startswith("//"):
        return "remoto"
    caminho = resolver(arquivo, limpo)
    if caminho is None:
        return "fora"
    if contexto.raiz is not None:
        raiz = contexto.raiz.resolve()
        real = (contexto.raiz / caminho).resolve()
        if real != raiz and raiz not in real.parents:
            return "fora"
    return None


def verificar(documento: Documento, contexto: Contexto) -> list[Problema]:
    """A R4.2 e a R4.3 nos elementos e nas folhas de um XHTML (ou de um SVG)."""
    problemas: list[Problema] = []
    for elemento in documento.elementos():
        problemas += _elemento(documento, elemento, contexto)
    for folha in folhas_do_documento(documento):
        problemas += verificar_folha(folha, contexto)
    return problemas


def _elemento(documento: Documento, elemento: Elemento, contexto: Contexto) -> list[Problema]:
    local = documento.local(elemento)
    problemas: list[Problema] = []
    if elemento.nome == "script":
        problemas.append(Problema(SCRIPT, local))
    if elemento.nome in EMBUTIDOS:
        problemas.append(Problema(EMBUTIDO, local, f"<{elemento.nome}>"))
    for atributo, valor in elemento.atributos.items():
        if atributo.lower().startswith("on") and "{" not in atributo:
            problemas.append(Problema(EVENTO, local, atributo))
        if atributo not in ENDERECOS:
            continue
        for endereco in _enderecos(atributo, valor):
            tipo = classificar(documento.arquivo, endereco, contexto)
            if tipo == "javascript":
                problemas.append(Problema(JAVASCRIPT, local, f"{atributo}={endereco[:60]!r}"))
            elif elemento.nome != "a" and atributo in RECURSOS.get(elemento.nome, ()):
                if tipo == "remoto":
                    problemas.append(Problema(REMOTO, local, endereco[:120]))
                elif tipo == "fora":
                    problemas.append(Problema(FORA, local, endereco[:120]))
    return problemas


def verificar_folha(folha: Folha, contexto: Contexto) -> list[Problema]:
    """O `@import` e o `url()` de uma folha: de fora da máquina ou fora do projeto."""
    problemas: list[Problema] = []
    for regra_ in folha.regras():
        if regra_.type == "at-rule" and regra_.lower_at_keyword == "import":
            endereco = next((n.value for n in nos_de(regra_.prelude)
                             if n.type in ("string", "url")), None)
            if endereco is None:
                endereco = next((texto for _, texto in urls(regra_.prelude)), None)
            if endereco is not None:
                tipo = classificar(folha.arquivo, endereco, contexto)
                if tipo == "remoto":
                    problemas.append(Problema(IMPORT, folha.local(regra_), endereco[:120]))
                elif tipo == "fora":
                    problemas.append(Problema(FORA, folha.local(regra_), endereco[:120]))
    for _, declaracao in folha.declaracoes():
        problemas += _urls(folha, declaracao.value, contexto)
    return problemas


def _urls(folha: Folha, valor: Iterable[object], contexto: Contexto) -> list[Problema]:
    problemas = []
    for no, endereco in urls(valor):
        tipo = classificar(folha.arquivo, endereco, contexto)
        if tipo == "remoto":
            problemas.append(Problema(REMOTO, folha.local(no), endereco[:120]))
        elif tipo in ("fora", "javascript"):
            problemas.append(Problema(FORA, folha.local(no), endereco[:120]))
    return problemas
