"""A camada de acessibilidade (spec S10 e §5.6): o WCAG 2.2 AA e o AAA que se aplica ao livro.

No XHTML: o `lang`; a hierarquia de títulos; o `alt` presente, e que não afirme o que ninguém
leu (o diagrama lido por máquina e não conferido diz isso, A9); as páginas (§5.6) — no capítulo,
o marcador da mesma página duas vezes (pelo número, qualquer que seja o `id`) e o número que
pula; na `page-list` do `nav`, a entrada repetida, a que pula e a que aponta para um marcador que
não existe; e, com o `nav` do livro no contexto, o marcador que a `page-list` não lista; a
imagem de texto (`img.cb-imagem-de-texto`, a região «mantida como imagem»: 1.4.5 AA e 1.4.9
AAA); `<audio>`/`<video>`/`<track>`; o interativo além do link (`<form>`, os controles,
`<details>`, `contenteditable`, `tabindex` > 0); o `meta refresh`; a imagem animada (GIF com
mais de um quadro, APNG, WebP e AVIF animados) em toda fonte de imagem — o `src` e o `srcset`
da `<img>` e da `<source>`, o `href` da `<image>` do SVG, o `data` do `<object>`, o `poster`; o
link sem propósito próprio (2.4.9: só «↩»); a seção sem papel (1.3.6); o símbolo fora do
glossário (3.1.3) e a abreviatura da lista sem `<abbr>` (3.1.4); o atributo com nome de campo de
proveniência (R2.4).

Nas folhas: `animation`, `transition` e `@keyframes` (2.3.3), e a imagem animada num `url()`
(o fundo, o marcador da lista); `position: fixed`/`sticky` (2.4.12); `:focus { outline: none }`
sem substituto (2.4.13).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from typing import Any

import tinycss2

from caissa.editor.validacao.contexto import Contexto, resolver
from caissa.editor.validacao.folha import Folha, folhas_do_documento, urls
from caissa.editor.validacao.problema import (
    Conserto,
    Problema,
    Severidade,
    Troca,
    regra,
)
from caissa.editor.validacao.xml import (
    EPUB_TYPE,
    XLINK_HREF,
    XML_LANG,
    Documento,
    Elemento,
    Trecho,
    ler,
)

__all__ = ["TITULOS_DAS_ABREVIATURAS", "verificar", "verificar_folha"]

A = "acessibilidade"
LANG = regra("a11y-lang", A, Severidade.AVISA, "O documento não diz a língua (3.1.1)",
             "Ponha lang e xml:lang na raiz <html> com a língua do livro.")
TITULO_SALTO = regra("a11y-titulo-salto", A, Severidade.AVISA,
                     "O título pula um nível (1.3.1, 2.4.10)",
                     "Use o nível seguinte ao do título de cima (um h2 depois do h1).")
ALT_AUSENTE = regra("a11y-alt-ausente", A, Severidade.BLOQUEIA,
                    "Imagem sem texto alternativo (1.1.1)",
                    "Dê à imagem um alt que diga o que ela mostra (alt=\"\" só na decorativa; "
                    "o diagrama sempre descreve a posição).")
ALT_AFIRMA = regra("a11y-alt-afirma", A, Severidade.AVISA,
                   "O alt afirma uma posição que ninguém conferiu (A9)",
                   "Diga no alt que a posição foi lida por máquina e não foi conferida, ou "
                   "confira o diagrama.")
PAGINA_DUPLICADA = regra("a11y-pagina-duplicada", A, Severidade.AVISA,
                         "Página duplicada (o marcador, ou a entrada da page-list)",
                         "Deixe um só marcador (e uma só entrada) por página impressa.")
PAGINA_LACUNA = regra("a11y-pagina-lacuna", A, Severidade.AVISA,
                      "Falta página (entre os marcadores, ou na page-list)",
                      "Ponha o marcador (e a entrada) da página que falta, ou confira o fólio.")
PAGINA_SEM_ALVO = regra("a11y-pagina-sem-alvo", A, Severidade.BLOQUEIA,
                        "A page-list aponta para um marcador de página que não existe",
                        "Corrija o href da entrada, ou ponha o marcador da página no capítulo.")
PAGINA_FORA_DA_LISTA = regra("a11y-pagina-fora-da-lista", A, Severidade.AVISA,
                             "Marcador de página fora da page-list do livro",
                             "Ponha a página na page-list do nav, ou tire o marcador.")
IMAGEM_DE_TEXTO = regra("a11y-imagem-de-texto", A, Severidade.AVISA,
                        "Região mantida como imagem de texto (1.4.5, 1.4.9)",
                        "Transcreva a região: o texto revisado substitui a imagem. Com imagem "
                        "de texto, o livro não declara conformidade.")
MIDIA = regra("a11y-midia", A, Severidade.BLOQUEIA, "Áudio ou vídeo no livro (1.2.x)",
              "Tire o elemento: o livro não tem mídia.")
INTERATIVO = regra("a11y-interativo", A, Severidade.BLOQUEIA,
                   "Interativo além do link (2.1.3)",
                   "Tire o controle: no livro só o <a href> é interativo.")
REFRESH = regra("a11y-refresh", A, Severidade.BLOQUEIA,
                "meta refresh: a página muda sozinha (2.2.x, 3.2.5)",
                "Tire o <meta http-equiv=\"refresh\">.")
ANIMACAO = regra("a11y-animacao", A, Severidade.BLOQUEIA,
                 "Animação no livro (2.3.3)",
                 "Tire a animação (animation, transition, @keyframes, a imagem animada).")
FIXO = regra("a11y-fixo", A, Severidade.AVISA,
             "position fixed ou sticky pode encobrir o foco (2.4.12)",
             "Tire o fixed/sticky: o conteúdo do livro rola junto.")
FOCO_APAGADO = regra("a11y-foco-apagado", A, Severidade.AVISA,
                     "O indicador de foco apagado sem substituto (2.4.13)",
                     "Não apague o outline no :focus, ou desenhe outro indicador na mesma regra.")
LINK_PROPOSITO = regra("a11y-link-proposito", A, Severidade.AVISA,
                       "O link não diz para onde vai (2.4.9)",
                       "Dê ao link um texto ou aria-label com o destino («voltar à nota 3»).")
REGIAO_SEM_PAPEL = regra("a11y-regiao-sem-papel", A, Severidade.AVISA,
                         "Seção sem papel (1.3.6)",
                         "Dê à seção um epub:type ou role (capítulo, nota…), ou use a classe "
                         "do contrato.")
SIMBOLO = regra("a11y-simbolo-fora-do-glossario", A, Severidade.AVISA,
                "Símbolo fora do glossário (3.1.3)",
                "Defina o símbolo no glossário do livro.")
ABREVIATURA = regra("a11y-abreviatura", A, Severidade.INFORMA,
                    "Abreviatura da lista sem <abbr> (3.1.4)",
                    "Marque com <abbr title=\"…\"> (há conserto).")
PROVENIENCIA = regra("a11y-proveniencia", A, Severidade.BLOQUEIA,
                     "Dado da máquina escrito no livro (R2.4)",
                     "Tire o atributo: a proveniência vai no proveniencia.json, não no livro.")

TITULOS_DAS_ABREVIATURAS: dict[str, str] = {
    "GM": "Grande Mestre", "MI": "Mestre Internacional", "MF": "Mestre FIDE",
    "WGM": "Grande Mestre Feminina", "WIM": "Mestre Internacional Feminina",
    "IM": "Mestre Internacional", "FM": "Mestre FIDE", "CM": "Candidato a Mestre",
    "FIDE": "Federação Internacional de Xadrez", "ECO": "Enciclopédia de Aberturas de Xadrez",
}
"""O `title` do `<abbr>` que o conserto põe (a lista do contrato, `Contexto.abreviaturas`)."""

INTERATIVOS = frozenset({"form", "input", "button", "select", "textarea", "details",
                         "summary", "option", "datalist", "output", "keygen", "menu"})
MIDIAS = frozenset({"audio", "video", "track"})
PAPEIS_DO_CONTRATO = frozenset({"cb-game", "cb-chapter", "cb-solution", "cb-resumo-simples"})
"""A seção com uma destas classes tem papel: o exportador (H24) põe o epub:type dela."""
CAMPOS_DE_PROVENIENCIA = frozenset({
    "data-confidence", "data-engine", "data-engine-version", "data-model-hash", "data-note",
    "data-extracted-at", "data-band", "data-dpi", "data-rect", "data-document-path",
    "data-document-hash", "data-block-index", "data-page-index", "data-confianca",
    "data-motor", "data-nota"})
QUALIFICADORES_DO_ALT = ("não conferida", "não reconhecida", "leitura provisória",
                         "not checked", "not recognised", "provisional reading")
"""O que o alt de um diagrama lido por máquina e não conferido diz (`export/diagrams.py`, A9)."""
FIGURINAS = frozenset("♔♕♖♗♘♙♚♛♜♝♞♟")
_DIGITOS_DO_ID = re.compile(r"(\d+)$")
_ROMANO = re.compile(r"^[ivxlcdm]+$")
_ROMANOS = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
_CABECA_DO_GIF = 13
"""A assinatura e o descritor da tela lógica."""
_EXTENSAO_DO_GIF = 0x21
_QUADRO_DO_GIF = 0x2C
_CABECA_DO_WEBP = 21
"""O `RIFF`, o `WEBP` e o `VP8X` até o byte das marcas."""
_FIXO = re.compile(r"^\s*(fixed|sticky|-webkit-sticky)\s*$", re.IGNORECASE)
_SEM_CONTORNO = re.compile(r"^\s*(none|0|0px|0em|0rem)\s*$", re.IGNORECASE)
_TITULO = re.compile(r"^h([1-6])$")
_SEM_ANIMACAO = frozenset({"none", "initial", "unset", "0", "0s", "0ms", "all 0s"})
SUBSTITUTOS_DO_FOCO = frozenset({"box-shadow", "border", "border-color", "border-bottom",
                                 "border-top", "border-left", "border-right", "background",
                                 "background-color", "text-decoration", "color",
                                 "outline-color", "text-decoration-line"})


def verificar(documento: Documento, contexto: Contexto) -> list[Problema]:
    """As regras de acessibilidade num XHTML (os elementos e as folhas de dentro dele)."""
    if documento.raiz is None:
        return []
    problemas = _lang(documento, contexto)
    problemas += _titulos(documento)
    problemas += _paginas(documento, contexto)
    for elemento in documento.elementos():
        problemas += _elemento(documento, elemento, contexto)
    problemas += _alts_de_diagrama(documento, contexto)
    problemas += _simbolos(documento, contexto)
    problemas += _abreviaturas(documento, contexto)
    for folha in folhas_do_documento(documento):
        problemas += verificar_folha(folha, contexto)
    return problemas


def _lang(documento: Documento, contexto: Contexto) -> list[Problema]:
    raiz = documento.raiz
    if raiz is None:
        return []
    if (raiz.get("lang") or "").strip() or (raiz.get(XML_LANG) or "").strip():
        return []
    idioma = contexto.idioma or "pt-BR"
    inicio = documento.deslocamento(raiz.linha, raiz.coluna) + 1 + len(raiz.nome)
    conserto = Conserto(f"Pôr lang e xml:lang = {idioma} na raiz",
                        (Troca(inicio, inicio, f' lang="{idioma}" xml:lang="{idioma}"'),))
    return [Problema(LANG, documento.local(raiz), conserto=conserto)]


def _titulos(documento: Documento) -> list[Problema]:
    problemas = []
    anterior = 0
    for elemento in documento.elementos():
        casado = _TITULO.match(elemento.nome)
        if casado is not None:
            nivel = int(casado.group(1))
            if anterior and nivel > anterior + 1:
                problemas.append(Problema(TITULO_SALTO, documento.local(elemento),
                                          f"h{anterior} → h{nivel}"))
            anterior = nivel
    return problemas


def _e_marcador(elemento: Elemento) -> bool:
    return ("pagebreak" in (elemento.get(EPUB_TYPE) or "").split()
            or elemento.get("role") == "doc-pagebreak")


def _e_lista_de_paginas(elemento: Elemento) -> bool:
    return elemento.nome == "nav" and (
        "page-list" in (elemento.get(EPUB_TYPE) or "").split()
        or elemento.get("role") == "doc-pagelist")


def _rotulo(marcador: Elemento) -> str:
    """O número impresso do marcador: o `aria-label`, o `title`, o texto, ou o fim do `id`."""
    for rotulo in (marcador.get("aria-label"), marcador.get("title"), marcador.texto()):
        if rotulo and rotulo.strip():
            return rotulo.strip()
    casado = _DIGITOS_DO_ID.search(marcador.get("id") or "")
    return casado.group(1) if casado else ""


def _numero(rotulo: str) -> tuple[str, int] | None:
    """A página como número, no sistema dela (o arábico e o romano não se misturam)."""
    texto = rotulo.strip().lower()
    if texto.isdigit():
        return "arábico", int(texto)
    if _ROMANO.match(texto):
        valores = [_ROMANOS[c] for c in texto]
        total = sum(-v if v < seguinte else v
                    for v, seguinte in zip(valores, [*valores[1:], 0], strict=True))
        return ("romano", total) if total > 0 else None
    return None


def _sequencia(documento: Documento, itens: list[tuple[Elemento, str]],
               onde: str) -> list[Problema]:
    """A página repetida (pelo número, ou pelo rótulo) e a que pula, na ordem dos itens."""
    problemas = []
    vistas: set[object] = set()
    anterior: dict[str, int] = {}
    for no, rotulo in itens:
        numero = _numero(rotulo)
        chave: object = numero if numero is not None else rotulo
        if rotulo and chave in vistas:
            problemas.append(Problema(PAGINA_DUPLICADA, documento.local(no),
                                      f"{onde}: a página {rotulo} de novo"))
            continue
        vistas.add(chave)
        if numero is None:
            continue
        sistema, valor = numero
        if sistema in anterior and valor > anterior[sistema] + 1:
            falta = ", ".join(str(n) for n in range(anterior[sistema] + 1, valor))
            problemas.append(Problema(PAGINA_LACUNA, documento.local(no),
                                      f"{onde}: {anterior[sistema]} → {valor}: falta {falta}"))
        anterior[sistema] = valor
    return problemas


def _marcadores_de(caminho: str, documento: Documento,
                   contexto: Contexto) -> dict[str, str] | None:
    """Os marcadores de página de um arquivo do projeto (`id` → rótulo); `None` se ele falta."""
    if caminho == documento.arquivo:
        return {e.get("id") or "": _rotulo(e) for e in documento.elementos() if _e_marcador(e)}
    guardados = contexto.guardado.setdefault("marcadores", {})
    if caminho not in guardados:
        texto = contexto.texto(caminho)
        if texto is None:
            guardados[caminho] = None
        else:
            lido, _ = ler(caminho, texto)
            guardados[caminho] = {e.get("id") or "": _rotulo(e) for e in lido.elementos()
                                  if _e_marcador(e)}
    return guardados[caminho]  # type: ignore[no-any-return]


def _entradas(lista: Elemento) -> list[Elemento]:
    return [a for a in lista.elementos() if a.nome == "a" and a.get("href") is not None]


def _alvo(documento: Documento, href: str) -> tuple[str | None, str]:
    return resolver(documento.arquivo, href), href.split("#", 1)[1] if "#" in href else ""


def _listados(contexto: Contexto) -> set[tuple[str, str]] | None:
    """As páginas que a `page-list` do `nav` do livro lista (o arquivo e o `id`), guardadas."""
    if contexto.nav is None:
        return None
    guardado = contexto.guardado
    if "listados" not in guardado:
        texto = contexto.texto(contexto.nav)
        listados: set[tuple[str, str]] | None = None
        if texto is not None:
            nav, _ = ler(contexto.nav, texto)
            listas = [e for e in nav.elementos() if _e_lista_de_paginas(e)]
            if listas:
                listados = set()
                for a in (a for lista in listas for a in _entradas(lista)):
                    caminho, fragmento = _alvo(nav, a.get("href") or "")
                    if caminho:
                        listados.add((caminho, fragmento))
        guardado["listados"] = listados
    return guardado["listados"]  # type: ignore[no-any-return]


def _paginas(documento: Documento, contexto: Contexto) -> list[Problema]:
    """As páginas do §5.6: os marcadores do capítulo, a `page-list` do `nav`, e o que falta nela."""
    marcadores = [e for e in documento.elementos() if _e_marcador(e)]
    problemas = _sequencia(documento, [(e, _rotulo(e)) for e in marcadores], "os marcadores")
    for lista in (e for e in documento.elementos() if _e_lista_de_paginas(e)):
        entradas = _entradas(lista)
        problemas += _sequencia(documento, [(a, a.texto().strip()) for a in entradas],
                                "a page-list")
        for a in entradas:
            caminho, fragmento = _alvo(documento, a.get("href") or "")
            alvos = _marcadores_de(caminho, documento, contexto) if caminho else None
            if alvos is None or fragmento not in alvos:
                problemas.append(Problema(PAGINA_SEM_ALVO, documento.local(a),
                                          a.get("href") or ""))
    listados = _listados(contexto) if contexto.nav != documento.arquivo else None
    if listados is not None:
        for marcador in marcadores:
            ident = marcador.get("id") or ""
            if (documento.arquivo, ident) not in listados:
                problemas.append(Problema(PAGINA_FORA_DA_LISTA, documento.local(marcador),
                                          ident or _rotulo(marcador)))
    return problemas


def _nome_acessivel(elemento: Elemento) -> str:
    rotulo = (elemento.get("aria-label") or "").strip()
    if rotulo:
        return rotulo
    partes = [elemento.texto()]
    partes += [(e.get("alt") or "") for e in elemento.elementos() if e.nome == "img"]
    return " ".join(partes).strip()


def _tem_letra_ou_numero(texto: str) -> bool:
    return any(unicodedata.category(c)[0] in "LN" for c in texto)


def _elemento(documento: Documento, elemento: Elemento, contexto: Contexto) -> list[Problema]:
    local = documento.local(elemento)
    problemas: list[Problema] = []
    nome = elemento.nome
    if nome == "img":
        problemas += _imagem(documento, elemento)
    problemas += _animada(documento, elemento, contexto)
    if nome in MIDIAS:
        problemas.append(Problema(MIDIA, local, f"<{nome}>"))
    problemas += _controles(documento, elemento)
    if nome == "meta" and (elemento.get("http-equiv") or "").strip().lower() == "refresh":
        problemas.append(Problema(REFRESH, local, elemento.get("content") or ""))
    if nome == "a" and elemento.get("href") is not None and \
            not _tem_letra_ou_numero(_nome_acessivel(elemento)):
        problemas.append(Problema(LINK_PROPOSITO, local, repr(_nome_acessivel(elemento))))
    if nome == "section" and not elemento.get("role") and not elemento.get(EPUB_TYPE) and \
            not PAPEIS_DO_CONTRATO.intersection(elemento.classes()):
        problemas.append(Problema(REGIAO_SEM_PAPEL, local))
    for atributo in elemento.atributos:
        if atributo.lower() in CAMPOS_DE_PROVENIENCIA:
            problemas.append(Problema(PROVENIENCIA, local, atributo))
    return problemas


def _imagem(documento: Documento, elemento: Elemento) -> list[Problema]:
    local = documento.local(elemento)
    problemas = []
    if elemento.get("alt") is None:
        problemas.append(Problema(ALT_AUSENTE, local, elemento.get("src") or ""))
    elif "cb-svg" in elemento.classes() and not (elemento.get("alt") or "").strip():
        problemas.append(Problema(ALT_AUSENTE, local, "o diagrama precisa descrever a posição"))
    if "cb-imagem-de-texto" in elemento.classes():
        problemas.append(Problema(IMAGEM_DE_TEXTO, local, elemento.get("src") or ""))
    return problemas


def _controles(documento: Documento, elemento: Elemento) -> list[Problema]:
    local = documento.local(elemento)
    problemas = []
    if elemento.nome in INTERATIVOS:
        problemas.append(Problema(INTERATIVO, local, f"<{elemento.nome}>"))
    editavel = elemento.get("contenteditable")
    if editavel is not None and editavel.strip().lower() != "false":
        problemas.append(Problema(INTERATIVO, local, "contenteditable"))
    ordem = (elemento.get("tabindex") or "").strip()
    if ordem.lstrip("+").isdigit() and int(ordem) > 0:
        problemas.append(Problema(INTERATIVO, local, f"tabindex={ordem}"))
    return problemas


def _candidatos(srcset: str) -> list[str]:
    """Os endereços de um `srcset` (cada candidato é o endereço e o descritor)."""
    return [candidato.split()[0] for candidato in srcset.split(",") if candidato.strip()]


def _fontes(elemento: Elemento) -> list[str]:
    """Toda fonte de imagem do elemento.

    O `src` e o `srcset` (a `<img>`, a `<source>`), o `href` da `<image>` do SVG, o `data` do
    `<object>`, o `poster`.
    """
    fontes: list[str] = []
    for atributo in ("src", "data", "poster"):
        valor = elemento.get(atributo)
        if valor and not (atributo == "src" and elemento.nome in ("script", "audio", "track")):
            fontes.append(valor)
    fontes += _candidatos(elemento.get("srcset") or "")
    if elemento.nome == "image":
        fontes += [v for v in (elemento.get("href"), elemento.get(XLINK_HREF)) if v]
    return fontes


def _animada(documento: Documento, elemento: Elemento, contexto: Contexto) -> list[Problema]:
    for fonte in _fontes(elemento):
        caminho = resolver(documento.arquivo, fonte)
        if caminho and animada(contexto.arquivos.get(caminho) or b""):
            return [Problema(ANIMACAO, documento.local(elemento), f"imagem animada: {caminho}")]
    return []


def animada(dados: bytes) -> bool:
    """A imagem tem mais de um quadro: o GIF, o APNG, o WebP e o AVIF animados."""
    return _gif_animado(dados) or _png_animado(dados) or _webp_animado(dados) or \
        _avif_animado(dados)


def _pular_sub_blocos(dados: bytes, posicao: int) -> int:
    while posicao < len(dados):
        tamanho = dados[posicao]
        posicao += 1
        if tamanho == 0:
            return posicao
        posicao += tamanho
    return posicao


def _gif_animado(dados: bytes) -> bool:
    """Um GIF com mais de um quadro (os descritores de imagem, pela estrutura dos blocos)."""
    if not dados.startswith((b"GIF87a", b"GIF89a")) or len(dados) < _CABECA_DO_GIF:
        return False
    tabela = dados[10]
    posicao = _CABECA_DO_GIF + (3 * 2 ** ((tabela & 7) + 1) if tabela & 0x80 else 0)
    quadros = 0
    while posicao < len(dados):
        bloco = dados[posicao]
        if bloco == _EXTENSAO_DO_GIF:  # uma extensão: o rótulo e os sub-blocos
            posicao = _pular_sub_blocos(dados, posicao + 2)
        elif bloco == _QUADRO_DO_GIF:  # um quadro: o descritor, a tabela local, o LZW
            quadros += 1
            if quadros > 1:
                return True
            if posicao + 10 > len(dados):
                break
            local = dados[posicao + 9]
            posicao += 10 + (3 * 2 ** ((local & 7) + 1) if local & 0x80 else 0) + 1
            posicao = _pular_sub_blocos(dados, posicao)
        else:  # o fim (0x3B) ou um byte que não é bloco
            break
    return False


def _png_animado(dados: bytes) -> bool:
    """Um PNG com o bloco `acTL` (o APNG) antes dos dados da imagem."""
    if not dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    posicao = 8
    while posicao + 8 <= len(dados):
        tamanho = int.from_bytes(dados[posicao:posicao + 4], "big")
        tipo = dados[posicao + 4:posicao + 8]
        if tipo == b"acTL":
            return True
        if tipo in (b"IDAT", b"IEND"):
            return False
        posicao += 12 + tamanho
    return False


def _webp_animado(dados: bytes) -> bool:
    """Um WebP com a marca de animação no `VP8X` (ou o bloco `ANIM`)."""
    if len(dados) < _CABECA_DO_WEBP or dados[:4] != b"RIFF" or dados[8:12] != b"WEBP":
        return False
    if dados[12:16] == b"VP8X":
        return bool(dados[20] & 0x02)
    return b"ANIM" in dados[12:4096]


def _avif_animado(dados: bytes) -> bool:
    """Um AVIF de sequência (a marca `avis` no `ftyp`)."""
    if dados[4:8] != b"ftyp":
        return False
    return b"avis" in dados[8:min(int.from_bytes(dados[:4], "big"), 256)]


def _alts_de_diagrama(documento: Documento, contexto: Contexto) -> list[Problema]:
    """O alt do diagrama lido por máquina e não conferido diz isso (A9); pede o mapa."""
    mapa = contexto.mapa
    if mapa is None:
        return []
    problemas = []
    for figura in documento.elementos():
        if figura.nome != "figure" or "cb-diagram" not in figura.classes():
            continue
        registro = mapa.nos.get(figura.get("id") or "")
        if registro is None or registro.conferido:
            continue
        leitura = registro.reconhecimento
        caminho = str(getattr(leitura, "path", "manual") or "manual")
        if leitura is None or caminho == "manual":
            continue
        for img in figura.elementos():
            if img.nome == "img" and "cb-svg" in img.classes():
                alt = (img.get("alt") or "").lower()
                if alt and not any(q in alt for q in QUALIFICADORES_DO_ALT):
                    problemas.append(Problema(ALT_AFIRMA, documento.local(img),
                                              figura.get("id") or ""))
    return problemas


def _trechos_do_texto(documento: Documento) -> Iterator[Trecho]:
    """Os trechos de texto corrido (fora de código, script, estilo e `<abbr>`)."""
    if documento.raiz is None:
        return
    for trecho in documento.raiz.trechos():
        nomes = {trecho.pai.nome, *(a.nome for a in trecho.pai.ancestrais())}
        if nomes & {"code", "pre", "script", "style", "abbr", "title"}:
            continue
        yield trecho


def _simbolos(documento: Documento, contexto: Contexto) -> list[Problema]:
    """Os NAG e as figurinas usados e que o glossário não define; pede o glossário."""
    if contexto.glossario is None:
        return []
    problemas = []
    vistos: set[str] = set()
    for elemento in documento.elementos():
        if "cb-nag" in elemento.classes():
            simbolo = elemento.texto().strip()
            if simbolo and simbolo not in contexto.glossario and simbolo not in vistos:
                vistos.add(simbolo)
                problemas.append(Problema(SIMBOLO, documento.local(elemento), simbolo))
    for trecho in _trechos_do_texto(documento):
        for deslocamento, caractere in enumerate(trecho.texto):
            if caractere in FIGURINAS and caractere not in contexto.glossario and \
                    caractere not in vistos:
                vistos.add(caractere)
                problemas.append(Problema(SIMBOLO, documento.local(trecho, deslocamento),
                                          caractere))
    return problemas


def _abreviaturas(documento: Documento, contexto: Contexto) -> list[Problema]:
    if not contexto.abreviaturas:
        return []
    padrao = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, sorted(
        contexto.abreviaturas, key=len, reverse=True))) + r")(?![\w-])")
    problemas = []
    for trecho in _trechos_do_texto(documento):
        for casado in padrao.finditer(trecho.texto):
            local = documento.local(trecho, casado.start())
            sigla = casado.group(1)
            inicio = documento.deslocamento(local.linha, local.coluna)
            titulo = TITULOS_DAS_ABREVIATURAS.get(sigla)
            conserto = Conserto(f"Marcar {sigla} com <abbr>", (Troca(
                inicio, inicio + len(sigla), f'<abbr title="{titulo}">{sigla}</abbr>'),)) \
                if titulo else None
            problemas.append(Problema(ABREVIATURA, local, sigla, conserto))
    return problemas


def verificar_folha(folha: Folha, contexto: Contexto) -> list[Problema]:
    """A animação (e a imagem animada num `url()`), o fixed/sticky e o foco apagado numa folha."""
    problemas: list[Problema] = [
        Problema(ANIMACAO, folha.local(regra_), "@keyframes") for regra_ in folha.regras()
        if regra_.type == "at-rule" and regra_.lower_at_keyword in ("keyframes",
                                                                     "-webkit-keyframes")]
    for _, declaracao in folha.declaracoes():
        for _no, endereco in urls(declaracao.value):
            caminho = resolver(folha.arquivo, endereco)
            if caminho and animada(contexto.arquivos.get(caminho) or b""):
                problemas.append(Problema(ANIMACAO, folha.local(declaracao),
                                          f"imagem animada: {caminho}"))
                break
    por_regra: dict[int, list[Any]] = {}
    regras: dict[int, Any] = {}
    for regra_, declaracao in folha.declaracoes():
        nome = declaracao.lower_name
        valor = _valor(declaracao)
        if nome.startswith(("animation", "transition", "-webkit-animation",
                            "-webkit-transition")) and valor.lower() not in _SEM_ANIMACAO:
            problemas.append(Problema(ANIMACAO, folha.local(declaracao), f"{nome}: {valor}"))
        if nome == "position" and _FIXO.match(valor):
            problemas.append(Problema(FIXO, folha.local(declaracao), valor))
        if regra_ is not None:
            por_regra.setdefault(id(regra_), []).append(declaracao)
            regras[id(regra_)] = regra_
    for chave, declaracoes in por_regra.items():
        regra_ = regras[chave]
        if getattr(regra_, "type", "") != "qualified-rule":
            continue
        seletor = _texto(regra_.prelude)
        if ":focus" not in seletor:
            continue
        apaga = next((d for d in declaracoes if d.lower_name in ("outline", "outline-style",
                                                                   "outline-width")
                      and _SEM_CONTORNO.match(_valor(d))), None)
        if apaga is None:
            continue
        if not any(d.lower_name in SUBSTITUTOS_DO_FOCO for d in declaracoes):
            problemas.append(Problema(FOCO_APAGADO, folha.local(apaga), seletor))
    return problemas


def _valor(declaracao: Any) -> str:
    return str(tinycss2.serialize(declaracao.value)).strip()


def _texto(nos: Any) -> str:
    return str(tinycss2.serialize(nos)).strip()
