r"""As dívidas da exportação que o editor poria na tela — o instrumento do passo H4.

A spec §2.7 lista dez defeitos do motor HTML/EPUB; o editor mostra a saída dele, e todo defeito
dela fica à vista. Este instrumento os **conta no livro exportado**, por sintoma, sem olhar o
código que o gerou — o mesmo contador serve para os EPUBs de antes (a sabotagem dos itens 3–9)
e para os de depois (o portão: todos zero).

Três modos:

- ``--epub <arquivo> [...] --saida <pasta>``: conta os dez sintomas em cada EPUB (com o sidecar
  de proveniência e o relatório de degradação ao lado, que ``--gerar`` grava) e grava
  ``dividas.json``, **por sintoma**: ``{"sintoma", "severidade": "bloqueia", "contagem",
  "exemplos": ["arquivo:linha", …]}``. Mede também se o alt de cada diagrama reconstrói a posição
  da FEN. Reprova com qualquer contagem > 0. ``--so-sintoma N`` conta um só (a sabotagem de um
  item sobre os EPUBs de antes).
- ``--gerar --saida <pasta> [--codigo <src>]``: exporta os três EPUBs do portão — ``LIVRO``
  p. 31–38, ``KEMERI`` p. 80, ``PEDIDO`` p. 55 — pelo ``export_book``, que é o que a CLI
  ``caissa.export.cli --epub`` chama, num processo com o ``src`` pedido (o desta árvore, ou o de
  uma árvore destacada no commit de antes do passo), e grava ao lado de cada um o relatório de
  degradação (``<livro>.degradacoes.json``).
- ``--fixtures --saida <pasta> [--sabotar …]``: as fixtures positivas dos itens 1, 2 e 10,
  montadas **como o produto monta** — o documento do importador real, ``LIVRO`` p. 31–38 (com
  ``Rect``, não tupla). ``--sabotar rect_como_lista``, ``estipulacao_sobrescrita`` e
  ``caminho_no_ir`` reintroduzem cada defeito por um remendo em memória, e a fixture dele
  reprova.

Uso::

    . .\benchmarks\editor_ambiente.ps1; Enter-AmbienteDosPortoes
    & $PY benchmarks\editor_dividas.py --gerar --saida benchmarks\reports\editor\h4\depois
    & $PY benchmarks\editor_dividas.py --epub <pasta dos EPUBs> --saida <pasta>
    & $PY benchmarks\editor_dividas.py --fixtures --saida <pasta>
"""

from __future__ import annotations

import argparse
import fnmatch
import getpass
import json
import os
import re
import subprocess
import sys
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

SABOTAGENS = ("rect_como_lista", "estipulacao_sobrescrita", "caminho_no_ir")

#: Os livros do portão (roadmap §0.2) e as páginas, em base 1 como a CLI as recebe.
LIVROS_DO_PORTAO: tuple[tuple[str, str, str], ...] = (
    ("livro", "AAGAARD - Practical Chess Defence.pdf", "31-38"),
    ("kemeri", "1937 Kemeri.pdf", "80"),
    ("pedido", "A Matter of Endgame Technique*Jacob Aagaard.pdf", "55"),
)

SINTOMAS: dict[int, tuple[str, str]] = {
    1: ("sidecar_sem_rect", "o sidecar de proveniência ausente, ou um registro de diagrama cujo "
        "rect não é {x, y, width, height, unit}"),
    2: ("estipulacao_sobrescrita", "a estipulação só do lado («Brancas jogam») num diagrama cuja "
        "legenda pede mais (mate, vitória, empate)"),
    3: ("alt_da_pagina", "o alt do diagrama é «Imagem da página N (W × H pt)»"),
    4: ("partida_com_interrogacao", "o cabeçalho da partida com «?» ou «· *», ou o lance em "
        "letras inglesas num livro que imprime figurinas"),
    5: ("fonte_de_xadrez_sem_uso", "uma face de xadrez embutida que nenhum texto usa"),
    6: ("svg_de_cor_fixa", "o SVG do diagrama com o fundo pintado e sem currentColor"),
    7: ("figurina_com_fonte_do_pdf", "a figurina com uma font-family que o pacote não embute"),
    8: ("verified_declarado_perdido", "a exportação declara perdido o verified_by_human que ela "
        "escreve"),
    9: ("diagrama_sem_numero", "o diagrama sem rótulo nem número (a numeração automática)"),
    10: ("caminho_local", "caminho absoluto, letra de unidade ou o nome do usuário no EPUB"),
}

XHTML = "{http://www.w3.org/1999/xhtml}"
SVG = "{http://www.w3.org/2000/svg}"
#: A pilha da `.piece` (html.PILHA_DE_FIGURINAS) e as famílias genéricas: nenhuma precisa ir no
#: pacote.
FAMILIAS_SEM_PACOTE = frozenset({
    "dejavu sans", "segoe ui symbol", "arial unicode ms", "serif", "sans-serif", "monospace",
    "cursive", "fantasy", "system-ui", "georgia", "times new roman", "inherit"})
LADO_SO = re.compile(r"^\s*(brancas|pretas) jogam\.?\s*$|^\s*(white|black) to (play|move)\.?\s*$",
                     re.I)
PEDE_MAIS = re.compile(r"\bmate\b|\bganha|\bempata|\bwin|\bdraw|#", re.I)
ALT_DA_PAGINA = re.compile(r"Imagem da página \d+ \(")
PECA_PT = re.compile(r"\b(Rei|Dama|Torre|Bispo|Cavalo|Peão|Peao) (branco|branca|preto|preta) em "
                     r"([a-h][1-8])\b")
PECA_EN = re.compile(r"\b(White|Black) (king|queen|rook|bishop|knight|pawn) on ([a-h][1-8])\b")
LETRA_PT = {"Rei": "k", "Dama": "q", "Torre": "r", "Bispo": "b", "Cavalo": "n", "Peão": "p",
            "Peao": "p"}
LETRA_EN = {"king": "k", "queen": "q", "rook": "r", "bishop": "b", "knight": "n", "pawn": "p"}
CAMINHO_LOCAL = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/](?![\\/])|\\\\[A-Za-z0-9_.-]+\\|"
                           r"/(?:Users|home)/|file:///", re.I)


# --------------------------------------------------------------------------- #
# O contador
# --------------------------------------------------------------------------- #


@dataclass
class Contagem:
    """Um sintoma: quantas vezes, e onde."""

    numero: int
    contagem: int = 0
    exemplos: list[str] = field(default_factory=list)

    def achou(self, onde: str, vezes: int = 1) -> None:
        self.contagem += vezes
        if len(self.exemplos) < 10:
            self.exemplos.append(onde)

    def como_dict(self) -> dict[str, Any]:
        nome, descricao = SINTOMAS[self.numero]
        return {"item": self.numero, "sintoma": nome, "descricao": descricao,
                "severidade": "bloqueia", "contagem": self.contagem, "exemplos": self.exemplos}


def _linha(texto: str, agulha: str) -> int:
    posicao = texto.find(agulha)
    return texto.count("\n", 0, posicao) + 1 if posicao >= 0 else 0


def _classes(elemento: Any) -> list[str]:
    return (elemento.get("class") or "").split()


def _regras_css(textos: list[str]) -> tuple[list[tuple[str, str]], set[str]]:
    """As regras `.classe { font-family: … }` na ordem, e as famílias dos `@font-face`."""
    regras: list[tuple[str, str]] = []
    embutidas: set[str] = set()
    for texto in textos:
        sem_comentario = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
        for bloco in re.finditer(r"@font-face\s*\{([^}]*)\}", sem_comentario):
            familia = re.search(r"font-family\s*:\s*([^;]+)", bloco.group(1))
            if familia:
                embutidas.add(familia.group(1).strip().strip("\"'").lower())
        for seletor, corpo in re.findall(r"([^{}@]+)\{([^{}]*)\}", sem_comentario):
            familia = re.search(r"font-family\s*:\s*([^;]+)", corpo)
            if familia:
                for parte in seletor.split(","):
                    casado = re.fullmatch(r"\s*[a-z]*\.([\w-]+)\s*", parte)
                    if casado:
                        regras.append((casado.group(1), familia.group(1).strip()))
    return regras, embutidas


def _familia_efetiva(classes: list[str], regras: list[tuple[str, str]]) -> str | None:
    """A `font-family` da última regra (na ordem das folhas) de uma das classes."""
    efetiva = None
    for classe, familia in regras:
        if classe in classes:
            efetiva = familia
    return efetiva


def _placement_do_alt(alt: str) -> str | None:
    """A posição que o alt descreve, como o campo de peças da FEN (ou `None` sem peça)."""
    casas: dict[str, str] = {}
    for peca, cor, casa in PECA_PT.findall(alt):
        letra = LETRA_PT[peca]
        casas[casa] = letra.upper() if cor.startswith("branc") else letra
    for cor, peca, casa in PECA_EN.findall(alt):
        letra = LETRA_EN[peca]
        casas[casa] = letra.upper() if cor == "White" else letra
    if not casas:
        return None
    linhas = []
    for fileira in range(8, 0, -1):
        linha, vazias = "", 0
        for coluna in "abcdefgh":
            letra = casas.get(f"{coluna}{fileira}")
            if letra is None:
                vazias += 1
                continue
            linha += (str(vazias) if vazias else "") + letra
            vazias = 0
        linhas.append(linha + (str(vazias) if vazias else ""))
    return "/".join(linhas)


def _usuario() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - sem usuário, só os caminhos contam
        return ""


def contar(  # noqa: PLR0912, PLR0915 - um laço por arquivo do pacote, um ramo por sintoma
        epub: Path, *, so: int | None = None) -> tuple[dict[int, Contagem], dict[str, Any]]:
    """Os dez sintomas num EPUB, e a conferência dos alts contra a FEN."""
    import xml.etree.ElementTree as ET

    from caissa.export.provenance import read_sidecar, sidecar_path

    contas = {n: Contagem(n) for n in SINTOMAS}
    alts = {"diagramas": 0, "batem": 0, "exemplos": []}
    nome = epub.name
    with zipfile.ZipFile(epub) as pacote:
        arquivos = {i.filename: pacote.read(i.filename) for i in pacote.infolist()
                    if not i.is_dir()}
    textos = {n: b.decode("utf-8", "replace") for n, b in arquivos.items()
              if n.lower().endswith((".xhtml", ".html", ".css", ".opf", ".ncx", ".xml", ".svg",
                                     ".json", ".txt", ".smil"))}
    regras, embutidas = _regras_css([t for n, t in textos.items() if n.lower().endswith(".css")])
    tem_figurinas = any('class="piece' in t for t in textos.values())
    familias_usadas: set[str] = set()

    for arquivo, texto in sorted(textos.items()):
        if not arquivo.lower().endswith((".xhtml", ".html")):
            continue
        try:
            raiz = ET.fromstring(texto.encode("utf-8"))  # noqa: S314 - o EPUB que se exportou
        except ET.ParseError:
            continue
        for elemento in raiz.iter():
            classes = _classes(elemento)
            efetiva = _familia_efetiva(classes, regras)
            if efetiva:
                familias_usadas.update(f.strip().strip("\"'").lower() for f in efetiva.split(","))
            if elemento.tag == f"{XHTML}figure" and "diagram" in classes:
                _contar_diagrama(elemento, arquivo, texto, contas, alts)
            elif elemento.tag == f"{XHTML}p" and "headers" in classes:
                cabecalho = "".join(elemento.itertext())
                if "?" in cabecalho or re.search(r"·\s*\*\s*$", cabecalho):
                    contas[4].achou(f"{arquivo}:{_linha(texto, cabecalho[:20])}")
            elif elemento.tag == f"{XHTML}span" and "move" in classes and tem_figurinas:
                lance = re.sub(r"^[\d.…\s]+", "", "".join(elemento.itertext()))
                if lance[:1] in {"K", "Q", "R", "B", "N"}:
                    contas[4].achou(f"{arquivo}:{_linha(texto, elemento.get('data-ir-id') or '')}")
            elif elemento.tag == f"{XHTML}span" and "piece" in classes and efetiva:
                primeira = efetiva.split(",")[0].strip().strip("\"'").lower()
                if primeira not in embutidas and primeira not in FAMILIAS_SEM_PACOTE:
                    contas[7].achou(f"{arquivo}:{_linha(texto, elemento.get('data-ir-id') or '')}")

    for familia in sorted(embutidas - familias_usadas):
        contas[5].achou(f"{nome}: @font-face «{familia}»")

    usuario = _usuario()
    for arquivo, texto in sorted(textos.items()):
        achados = CAMINHO_LOCAL.findall(texto)
        if usuario:
            # O nome do usuário só num caminho (`\ana\`, `/ana/`): uma palavra do livro não conta.
            achados += re.findall(rf"[\\/]{re.escape(usuario)}[\\/]", texto, re.I)
        if achados:
            contas[10].achou(f"{arquivo}:{_linha(texto, achados[0])}", len(achados))

    sidecar = sidecar_path(epub)
    if not sidecar.is_file():
        contas[1].achou(f"{sidecar.name}: o sidecar não foi gravado")
    else:
        _, registros = read_sidecar(sidecar)
        for chave, registro in registros.items():
            if registro.get("kind") != "diagram":
                continue
            for rect in (registro.get("rect"), (registro.get("provenance") or {}).get("rect")):
                if rect is not None and not (isinstance(rect, dict) and {
                        "x", "y", "width", "height", "unit"} <= set(rect)):
                    contas[1].achou(f"{sidecar.name}: {chave}")

    degradacoes = epub.with_suffix(".degradacoes.json")
    if not degradacoes.is_file():
        contas[8].achou(f"{degradacoes.name}: o relatório de degradação não foi gravado")
    else:
        for aviso in json.loads(degradacoes.read_text(encoding="utf-8")):
            if "verified_by_human" in str(aviso.get("property", "")):
                contas[8].achou(f"{degradacoes.name}: {aviso.get('node_id')}")
    if so is not None:
        contas = {so: contas[so]}
    return contas, alts


def _contar_diagrama(figura: Any, arquivo: str, texto: str, contas: dict[int, Contagem],
                     alts: dict[str, Any]) -> None:
    agulha = figura.get("data-ir-id") or 'class="diagram"'
    onde = f"{arquivo}:{_linha(texto, agulha)}"
    legenda = " ".join("".join(e.itertext()) for e in figura.iter(f"{XHTML}figcaption"))
    estipulacao = figura.get("data-stipulation") or ""
    if LADO_SO.match(estipulacao) and PEDE_MAIS.search(legenda.replace(estipulacao, "")):
        contas[2].achou(onde)
    svg = next(figura.iter(f"{SVG}svg"), None)
    alt = ""
    if svg is not None:
        titulo = next(svg.iter(f"{SVG}title"), None)
        alt = svg.get("aria-label") or ("".join(titulo.itertext()) if titulo is not None else "")
        corpo = ET_tostring(svg)
        fundo = re.search(r'<(?:\w+:)?rect[^>]*\bx="0"[^>]*\by="0"[^>]*\bfill="#', corpo)
        if fundo or "currentColor" not in corpo:
            contas[6].achou(onde)
    if ALT_DA_PAGINA.search(alt):
        contas[3].achou(onde)
    alts["diagramas"] += 1
    fen = (figura.get("data-fen") or "").split(" ")[0]
    if _placement_do_alt(alt) == fen or (not fen and not _placement_do_alt(alt)):
        alts["batem"] += 1
    elif len(alts["exemplos"]) < 10:
        alts["exemplos"].append(f"{onde}: {alt[:80]}")
    if not (figura.get("data-number") or figura.get("data-label") or any(
            "label" in _classes(e) for e in figura.iter())):
        contas[9].achou(onde)


def ET_tostring(elemento: Any) -> str:  # noqa: N802 - o nome do ElementTree
    import xml.etree.ElementTree as ET

    return ET.tostring(elemento, encoding="unicode")


# --------------------------------------------------------------------------- #
# Gerar os EPUBs do portão
# --------------------------------------------------------------------------- #


def _principal() -> Path:
    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    return Path(comum).parent if comum else RAIZ


def livro_do_portao(padrao: str) -> Path:
    pasta = _principal().parent / "ChessVisionOFF_Puro" / "PDF"
    achados = sorted(p for p in pasta.glob("*.pdf") if fnmatch.fnmatch(p.name, padrao))
    if not achados:
        raise FileNotFoundError(f"livro ausente em {pasta}: {padrao}")
    return achados[0]


_EXPORTAR = """
import json, sys
sys.path.insert(0, sys.argv[1])
from caissa.export.book import export_book
resultado = export_book(sys.argv[2], sys.argv[3], "epub", pages=sys.argv[4])
avisos = [{"property": w.property, "node_type": w.node_type, "node_id": str(w.node_id),
           "message": w.message} for w in resultado.export_result.degradation.warnings]
open(sys.argv[5], "w", encoding="utf-8").write(json.dumps(avisos, ensure_ascii=False, indent=1))
print(resultado.summary())
"""


def gerar(saida: Path, codigo: Path) -> list[Path]:
    """Os três EPUBs do portão pelo `export_book` do `src` pedido, com o relatório ao lado."""
    saida.mkdir(parents=True, exist_ok=True)
    gerados = []
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8",
                "PYTHONPATH": os.pathsep.join([str(codigo)])}
    for nome, padrao, paginas in LIVROS_DO_PORTAO:
        destino = saida / f"{nome}.epub"
        subprocess.run(  # noqa: S603 - o Python e os argumentos são nossos
            [sys.executable, "-c", _EXPORTAR, str(codigo), str(livro_do_portao(padrao)),
             str(destino), paginas, str(destino.with_suffix(".degradacoes.json"))],
            check=True, env=ambiente, cwd=RAIZ)
        gerados.append(destino)
    return gerados


# --------------------------------------------------------------------------- #
# As fixtures positivas dos itens 1, 2 e 10
# --------------------------------------------------------------------------- #


def importar_livro() -> Any:
    """O documento do importador real: `LIVRO` p. 31–38, sem OCR (as páginas são nativas)."""
    from caissa.ingest.pdf.importer import PdfImportOptions, import_pdf

    return import_pdf(livro_do_portao(LIVROS_DO_PORTAO[0][1]),
                      PdfImportOptions(pages=list(range(30, 38)), enable_ocr=False))


def _diagramas(documento: Any) -> list[Any]:
    from caissa.core.model import Diagram

    return [b for b in documento.body if isinstance(b, Diagram)]


def fixture_rect(importado: Any, pasta: Path) -> list[str]:
    """(1) O sidecar é gravado, e cada registro de diagrama tem o `rect` inteiro.

    O `rect` com x, y, largura, altura e unidade: o conserto do item 1 da spec §2.7.
    """
    from caissa.export.book import export_book
    from caissa.export.provenance import read_sidecar, sidecar_path

    destino = pasta / "fixture_1.epub"
    resultado = export_book(livro_do_portao(LIVROS_DO_PORTAO[0][1]), destino, "epub",
                            document=importado)
    faltas = []
    if resultado.provenance_error:
        faltas.append(f"o sidecar não foi gravado: {resultado.provenance_error}")
        return faltas
    _, registros = read_sidecar(sidecar_path(destino))
    diagramas = [r for r in registros.values() if r.get("kind") == "diagram"]
    if not diagramas:
        faltas.append("o sidecar não tem registro de diagrama")
    for registro in diagramas:
        rect = registro.get("rect")
        if not (isinstance(rect, dict) and {"x", "y", "width", "height", "unit"} <= set(rect)):
            faltas.append(f"o registro {registro.get('id')} tem rect {rect!r}")
    return faltas


def fixture_estipulacao(importado: Any) -> list[str]:
    """(2) Um diagrama com «Mate em 2» e uma decisão de lado mantém «Mate em 2»."""
    from dataclasses import replace

    from caissa.export.book import apply_diagram_decisions
    from caissa.ingest.pdf.importer import ImportResult
    from caissa.ocr.diagram_decisions import DiagramDecision, DiagramDecisions

    candidatos = [d for d in _diagramas(importado.document)
                  if d.source is not None and d.source.rect is not None and d.fen]
    if not candidatos:
        return ["o LIVRO p. 31-38 não trouxe diagrama com recorte"]
    alvo = candidatos[0]
    campos = alvo.fen.split()
    lado = "b" if (campos[1:2] or ["w"])[0] == "w" else "w"
    fen_decidida = " ".join([campos[0], lado, *campos[2:]]) if len(campos) > 1 else \
        f"{campos[0]} {lado} - - 0 1"
    com_estipulacao = replace(alvo, stipulation="Mate em 2")
    corpo = tuple(com_estipulacao if b is alvo else b for b in importado.document.body)
    documento = replace(importado.document, body=corpo)
    rect = alvo.source.rect
    decisao = DiagramDecision(
        page_index=int(alvo.source.page_index or 0),
        rect=(rect.x, rect.y, rect.x + rect.width, rect.y + rect.height),
        fen=fen_decidida, side=lado, decided_at="2026-09-24T00:00:00Z", reviewer="fixture",
        source="janela", note="fixture do H4, item 2")
    depois = apply_diagram_decisions(ImportResult(document=documento, report=importado.report),
                                     DiagramDecisions(items=(decisao,)))
    decidido = next(d for d in _diagramas(depois.document) if d.id == alvo.id)
    faltas = []
    if decidido.fen != fen_decidida:
        faltas.append("a decisão não foi aplicada ao diagrama")
    if decidido.stipulation != "Mate em 2":
        faltas.append(f"a estipulação virou {decidido.stipulation!r}")
    return faltas


def fixture_caminho(pasta: Path) -> list[str]:
    """(10) Nenhum arquivo do EPUB tem letra de unidade, caminho absoluto ou o nome do usuário."""
    destino = pasta / "fixture_1.epub"
    if not destino.is_file():
        return ["o EPUB da fixture 1 não existe"]
    contas, _ = contar(destino, so=10)
    return [f"{c.contagem} caminho(s) local(is): {c.exemplos[:3]}" for c in contas.values()
            if c.contagem]


def remendo(sabotagem: str | None) -> Callable[[], None]:
    """Reintroduz um defeito por remendo em memória; devolve o que o desfaz."""
    if sabotagem is None:
        return lambda: None
    from caissa.export import book, epub, provenance

    alvos: dict[str, tuple[Any, str, Any]] = {
        "rect_como_lista": (provenance, "_rect_record",
                            lambda r: [r.x, r.y, r.width, r.height] if r else None),
        "estipulacao_sobrescrita": (book, "_stipulation_after_decision",
                                    lambda _atual, lado: "Brancas jogam" if lado == "w"
                                    else "Pretas jogam"),
        "caminho_no_ir": (epub, "_portable_path", lambda valor: valor),
    }
    modulo, nome, falso = alvos[sabotagem]
    original = getattr(modulo, nome)
    setattr(modulo, nome, falso)
    return lambda: setattr(modulo, nome, original)


def rodar_fixtures(pasta: Path, sabotagem: str | None) -> dict[str, list[str]]:
    pasta.mkdir(parents=True, exist_ok=True)
    desfazer = remendo(sabotagem)
    try:
        importado = importar_livro()
        resultado = {"1_rect": fixture_rect(importado, pasta),
                     "2_estipulacao": fixture_estipulacao(importado)}
        resultado["10_caminho"] = fixture_caminho(pasta)
    finally:
        desfazer()
    return resultado


# --------------------------------------------------------------------------- #
# O EPUBCheck
# --------------------------------------------------------------------------- #


def jar_do_epubcheck() -> Path | None:
    """O `epubcheck.jar` para o portão.

    O desta árvore, o do checkout principal (o `tools/` que o git ignora), ou o que o produto
    acha (`caissa.export.epubcheck.find_epubcheck_jar`).
    """
    for base in (RAIZ, _principal()):
        achados = sorted((base / "tools").glob("epubcheck-*/epubcheck.jar"))
        if achados:
            return achados[-1]
    from caissa.export.epubcheck import find_epubcheck_jar

    return find_epubcheck_jar()


def epubcheck(epubs: list[Path]) -> dict[str, Any]:
    """Os erros e avisos do EPUBCheck em cada EPUB; sem o validador, o portão reprova."""
    from caissa.export.epubcheck import run_epubcheck

    jar = jar_do_epubcheck()
    if jar is None:
        return {"erro": "o EPUBCheck não foi achado (tools/epubcheck-*/epubcheck.jar)"}
    resultado: dict[str, Any] = {"jar": str(jar), "livros": {}}
    for epub in epubs:
        try:
            medido = run_epubcheck(jar, epub)
        except OSError as falha:
            return {"erro": f"o Java não abriu: {falha}"}
        resultado["livros"][epub.name] = {"erros": medido.errors, "avisos": medido.warnings,
                                          "saida": medido.output[-2000:]}
    return resultado


# --------------------------------------------------------------------------- #
# A linha de comando
# --------------------------------------------------------------------------- #


def _epubs(caminhos: list[Path]) -> Iterator[Path]:
    for caminho in caminhos:
        if caminho.is_dir():
            yield from sorted(caminho.glob("*.epub"))
        else:
            yield caminho


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915 - os três modos do portão
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--epub", type=Path, nargs="*", default=[])
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--so-sintoma", type=int, choices=sorted(SINTOMAS))
    parser.add_argument("--gerar", action="store_true")
    parser.add_argument("--codigo", type=Path, default=RAIZ / "src")
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    parser.add_argument("--epubcheck", action="store_true",
                        help="valida cada EPUB com o EPUBCheck (o portão exige 0 erro)")
    args = parser.parse_args(argv)
    args.saida.mkdir(parents=True, exist_ok=True)

    if args.fixtures:
        resultado = rodar_fixtures(args.saida, args.sabotar)
        (args.saida / "fixtures.json").write_text(
            json.dumps({"sabotagem": args.sabotar, "fixtures": resultado}, ensure_ascii=False,
                       indent=1), encoding="utf-8")
        for nome, faltas in resultado.items():
            print(f"{'PASSOU' if not faltas else 'REPROVADO'}: fixture {nome}"
                  + ("" if not faltas else " -- " + "; ".join(faltas)))
        return 0 if not any(resultado.values()) else 1

    epubs = list(_epubs(args.epub))
    if args.gerar:
        epubs = gerar(args.saida, args.codigo)
    if not epubs:
        parser.error("nada a contar: --epub, --gerar ou --fixtures")
    relatorio: dict[str, Any] = {}
    totais = dict.fromkeys(SINTOMAS, 0)
    alts_ruins = 0
    for epub in epubs:
        contas, alts = contar(epub, so=args.so_sintoma)
        relatorio[epub.name] = {"sintomas": [c.como_dict() for c in contas.values()],
                                "alts": alts}
        for numero, conta in contas.items():
            totais[numero] += conta.contagem
        if args.so_sintoma is None:
            alts_ruins += alts["diagramas"] - alts["batem"]
    (args.saida / "dividas.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    metricas = {f"sintoma_{n}": totais[n] for n in (
        [args.so_sintoma] if args.so_sintoma else SINTOMAS)}
    metricas["alts_que_nao_batem"] = alts_ruins
    (args.saida / "metricas.json").write_text(json.dumps(metricas, indent=1), encoding="utf-8")
    ok = True
    for numero in ([args.so_sintoma] if args.so_sintoma else SINTOMAS):
        nome, descricao = SINTOMAS[numero]
        passou = totais[numero] == 0
        ok &= passou
        print(f"{'PASSOU' if passou else 'REPROVADO'}: sintoma {numero} ({nome}) = "
              f"{totais[numero]} em {len(epubs)} EPUB(s) -- {descricao}")
    if args.so_sintoma is None:
        print(f"{'PASSOU' if not alts_ruins else 'REPROVADO'}: alts que não reconstroem a FEN = "
              f"{alts_ruins}")
        ok &= not alts_ruins
    if args.epubcheck:
        validado = epubcheck(epubs)
        (args.saida / "epubcheck.json").write_text(
            json.dumps(validado, ensure_ascii=False, indent=1), encoding="utf-8")
        if "erro" in validado:
            print(f"REPROVADO: EPUBCheck -- {validado['erro']}")
            ok = False
        else:
            # `-1` é a quebra do validador: nunca soma como zero.
            ruins = [n for n, v in validado["livros"].items() if v["erros"] != 0]
            erros = sum(abs(v["erros"]) for v in validado["livros"].values())
            avisos = sum(max(0, v["avisos"]) for v in validado["livros"].values())
            print(f"{'PASSOU' if not ruins else 'REPROVADO'}: EPUBCheck = {erros} erro(s) e "
                  f"{avisos} aviso(s) em {len(epubs)} EPUB(s)"
                  + (f" -- {', '.join(ruins)}" if ruins else ""))
            ok &= not ruins
            metricas["epubcheck_erros"] = erros
            (args.saida / "metricas.json").write_text(json.dumps(metricas, indent=1),
                                                      encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
