r"""A ida e a volta do perfil legível — o portão do passo H5 do Editor HTML/CSS.

1. **A ida** IR → XHTML legível → IR, pelo `semantic_diff` contra a forma normal
   (`caissa.export.legivel.forma_normal`, as normalizações N1–N4 do contrato), com o mapa da
   proveniência passando pelo `proveniencia.json` (formato 2): o corpus sintético de 10 mil nós
   (semente 42) e o IR real — `LIVRO` p. 31–38, `KEMERI` p. 80, `PEDIDO` p. 50–60 e `DEM`
   p. 20–25, pelo importador do produto sem OCR (as páginas têm camada de texto). **0 diferença**,
   e as N1–N4 contadas.
2. **A volta** XHTML → IR → XHTML, pelo `canon`: as fixtures do contrato (H3 e §12), os arquivos
   da ida e as edições à mão de `tests/fixtures/editor/editados/` (ao menos 20). **100 %.**
3. **O CSS byte a byte:** cada folha do projeto (`Resource(kind=STYLESHEET)`) vai ao EPUB do arnês
   pelo `folhas_do_livro` e volta dele igual. **100 %.**
4. **O mapa de estilo** nas fixtures do H3: as positivas com o estilo esperado, as negativas com o
   aviso esperado. **100 %.**
5. **O CB validate** nas fixtures, nos capítulos do IR real e nas edições: **0 erro de contrato**
   (o erro de conteúdo do livro — o diagrama que não é a posição do lance acima dele — é contado
   à parte e não reprova: o contrato não o decide); e, nas fixtures e em todos os arquivos da ida,
   **nada que o CB confunda sem acusar** (o MARKUP §10): nenhum elemento que uma expressão do
   `validate.py` case sem ter a classe dela, e nenhum `cb-move` sem `data-fen`, que ele pula.
6. **O EPUBCheck** num EPUB montado no arnês com os capítulos legíveis do IR real, as folhas e as
   imagens: **0 erro**.

**Sabotagens** (`--sabotar`), cada uma tem de reprovar: `perde_fen` (o escritor não escreve o
`data-fen` do diagrama), `perde_classe` (o escritor perde a classe do estilo),
`engole_desconhecido` (o leitor descarta o elemento fora do contrato em vez de preservá-lo),
`perde_atributo` (o leitor ignora os atributos preservados), `css_silencioso` (o mapa de estilo não
avisa a regra fora dele), `nula` (o escritor não escreve nada) e `lance_sem_fen` (o lance que não
se joga volta ao `cb-move` sem `data-fen`, a forma que o ciclo 1 do crítico reprovou).

O IR real é caro de importar: `--gerar-ir-real <pasta>` o importa uma vez e o guarda (o JSON do
IR, com o SHA-256 do PDF e o commit ao lado); `--ir-real <pasta>` o usa.

Uso::

    & $PY benchmarks\editor_ida_e_volta.py --gerar-ir-real benchmarks\reports\editor\h5_ir_real
    & $PY benchmarks\editor_ida_e_volta.py --ir-real benchmarks\reports\editor\h5_ir_real `
        --saida benchmarks\reports\editor\h5\1
    & $PY benchmarks\editor_ida_e_volta.py --ir-real benchmarks\reports\editor\h5_ir_real `
        --sabotar perde_fen --saida benchmarks\reports\editor\h5\perde_fen
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

FIXTURES = RAIZ / "tests" / "fixtures" / "editor"
CONTRATO = FIXTURES / "contrato"
EDITADOS = FIXTURES / "editados"
CSS = FIXTURES / "css"
MODELO = RAIZ / "tests" / "unit" / "model"
"""Onde mora o gerador do corpus sintético (`generators.NodeFactory`)."""

NOS_DO_CORPUS = 10_000
SEMENTE = 42
EDICOES_MINIMAS = 20
LIVROS_REAIS: tuple[tuple[str, str, tuple[int, ...]], ...] = (
    ("livro", "AAGAARD - Practical Chess Defence*", tuple(range(30, 38))),
    ("kemeri", "1937 Kemeri*", (79,)),
    ("pedido", "A Matter of Endgame Technique*", tuple(range(49, 60))),
    ("dem", "Dvoretsky - Dvoretsky*", tuple(range(19, 25))),
)
"""O nome, o arquivo e as páginas (base 0) de cada livro do IR real."""
SABOTAGENS = ("perde_fen", "perde_classe", "engole_desconhecido", "perde_atributo",
              "css_silencioso", "nula", "lance_sem_fen")
ERROS_DE_CONTEUDO = ("Diagram does not show the position of the move above it",)
"""Os erros do CB que são do conteúdo do livro, e não do contrato de marcação."""


# --------------------------------------------------------------------------- #
# Os livros e o IR real
# --------------------------------------------------------------------------- #


def _principal() -> Path:
    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    return Path(comum).parent if comum else RAIZ


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ,  # noqa: S607
                          capture_output=True, text=True, check=False).stdout.strip()


def livro_do_portao(padrao: str) -> Path:
    pasta = _principal().parent / "ChessVisionOFF_Puro" / "PDF"
    achados = sorted(p for p in pasta.glob("*.pdf") if fnmatch.fnmatch(p.name, padrao))
    if not achados:
        raise FileNotFoundError(f"livro ausente em {pasta}: {padrao}")
    return achados[0]


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def gerar_ir_real(pasta: Path) -> list[Path]:
    """Importa as páginas do portão pelo importador do produto (sem OCR) e guarda o IR."""
    from caissa.core.model.serialize import dumps
    from caissa.ingest.pdf.importer import PdfImportOptions, import_pdf

    pasta.mkdir(parents=True, exist_ok=True)
    gerados = []
    for nome, padrao, paginas in LIVROS_REAIS:
        pdf = livro_do_portao(padrao)
        resultado = import_pdf(pdf, PdfImportOptions(pages=list(paginas), enable_ocr=False))
        destino = pasta / f"{nome}.ir.json"
        destino.write_text(dumps(resultado.document), encoding="utf-8")
        (pasta / f"{nome}.origem.json").write_text(json.dumps({
            "pdf": pdf.name, "sha256": _sha256(pdf), "paginas": [p + 1 for p in paginas],
            "commit": _head(), "ocr": False}, ensure_ascii=False, indent=1), encoding="utf-8")
        gerados.append(destino)
    return gerados


def carregar_ir_real(pasta: Path) -> dict[str, Any]:
    """O IR real guardado pelo `--gerar-ir-real`, por livro; o que falta, falta."""
    from caissa.core.model.serialize import loads

    documentos: dict[str, Any] = {}
    for nome, _, _ in LIVROS_REAIS:
        arquivo = pasta / f"{nome}.ir.json"
        if arquivo.is_file():
            documentos[nome] = loads(arquivo.read_text(encoding="utf-8"))
    return documentos


def corpus_sintetico(nos: int, semente: int) -> Any:
    if str(MODELO) not in sys.path:
        sys.path.insert(0, str(MODELO))
    from generators import NodeFactory

    return NodeFactory(semente).document(min_nodes=nos)


# --------------------------------------------------------------------------- #
# A ida
# --------------------------------------------------------------------------- #


def ida(documento: Any, nome: str, pasta: Path) -> dict[str, Any]:
    """IR → XHTML legível → IR, com o mapa pelo JSON; as diferenças fora da forma normal."""
    from caissa.core.model import Document, semantic_diff
    from caissa.editor.leitura import (
        conferir_mapa,
        mapa_de_json,
        mapa_para_json,
        nomes_de_estilo,
    )
    from caissa.export.legivel import Capitulo, escrever_capitulo, forma_normal, ler_capitulo

    capitulo = Capitulo(blocos=documento.body, titulo=nome, folhas=("../Styles/livro.css",),
                        idioma=documento.metadata.language or "pt-BR")
    try:
        texto, escritor = escrever_capitulo(capitulo, documento)
    except ValueError as falha:
        return {"erro": f"o escritor recusou: {falha}", "diferencas": None}
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.xhtml").write_text(texto, encoding="utf-8", newline="\n")
    mapa = mapa_para_json(escritor.mapa)
    (pasta / f"{nome}.proveniencia.json").write_text(
        json.dumps(mapa, ensure_ascii=False, indent=1), encoding="utf-8")
    imagens = pasta / "Images"
    imagens.mkdir(exist_ok=True)
    for arquivo, svg in escritor.imagens.items():
        if svg:
            (imagens / arquivo).write_text(svg, encoding="utf-8", newline="\n")
    mapa_lido = mapa_de_json(json.loads(json.dumps(mapa)))
    try:
        relido = ler_capitulo(texto, mapa=mapa_lido, estilos=nomes_de_estilo(documento))
    except (ValueError, KeyError) as falha:
        return {"erro": f"o leitor não leu o que o escritor escreveu: {falha}",
                "diferencas": None}
    normal, contagem = forma_normal(documento.body)
    # A N3 sem perda: cada dado da máquina que sai do IR está no mapa, e acha o lugar dele.
    n3 = sum(n for chave, n in contagem.items() if chave.startswith("N3:"))
    problemas_do_mapa = conferir_mapa(relido, mapa_lido)
    relatorio = semantic_diff(Document(metadata=documento.metadata, body=normal),
                              Document(metadata=documento.metadata, body=relido.blocos),
                              ignore_ids=True)
    por_classe: Counter[str] = Counter()
    for chave, n in contagem.items():
        por_classe[chave.split(":")[0]] += n
    return {"nos": relatorio.left_node_count, "diferencas": len(relatorio.entries),
            "n3": n3, "n3_guardada": mapa_lido.registros(),
            "mapa_fora_do_lugar": len(problemas_do_mapa),
            "mapa_problemas": problemas_do_mapa[:10],
            "exemplos": [f"{e.kind} {e.node_type}.{e.field or ''} em {e.path}: "
                         f"{(e.before or '')[:120]} -> {(e.after or '')[:120]}"
                         for e in relatorio.entries[:10]],
            "normalizacoes": dict(sorted(por_classe.items())),
            "normalizacoes_por_campo": dict(contagem.most_common(60)),
            "bytes": len(texto.encode("utf-8"))}


# --------------------------------------------------------------------------- #
# A volta, o CSS, o mapa, o CB e o EPUBCheck
# --------------------------------------------------------------------------- #


def arquivos_da_volta(pasta_da_ida: Path) -> list[Path]:
    """As fixtures do contrato (sem a legada), os arquivos da ida e as edições à mão."""
    fixtures = sorted(p for p in CONTRATO.glob("*.xhtml") if not p.name.startswith("legado"))
    return [*fixtures, *sorted(pasta_da_ida.glob("*.xhtml")), *sorted(EDITADOS.glob("*.xhtml"))]


def brutos_esperados() -> dict[str, list[str]]:
    """O que a conferência pode guardar como bruto em cada edição à mão (`esperado.json`)."""
    arquivo = EDITADOS / "esperado.json"
    if not arquivo.is_file():
        return {}
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    return {nome: registro["esperado"] for nome, registro in dados["brutos"].items()}


def volta(arquivos: Sequence[Path]) -> dict[str, Any]:
    """canon(escrever(ler(x))) == canon(x) em cada arquivo, e o que a conferência pôs em bruto.

    O leitor guarda como bruto o elemento que a reescrita não devolve igual — nada se perde, mas
    o nó do IR também não existe. Nas fixtures do contrato e nos arquivos da ida isso não pode
    acontecer; nas edições à mão, só onde o `esperado.json` diz.
    """
    from caissa.editor.leitura import ler_legivel
    from caissa.export.legivel import canon, escrever_capitulo

    esperados = brutos_esperados()
    diferentes: list[str] = []
    brutos_fora: list[str] = []
    for arquivo in arquivos:
        texto = arquivo.read_text(encoding="utf-8")
        try:
            capitulo = ler_legivel(texto)
            escrito, _ = escrever_capitulo(capitulo)
            igual = canon(escrito) == canon(texto)
        except (ValueError, KeyError, TypeError) as falha:
            diferentes.append(f"{arquivo.name} ({type(falha).__name__}: {falha})")
            continue
        if not igual:
            diferentes.append(arquivo.name)
        permitidos = esperados.get(arquivo.name, []) if arquivo.parent == EDITADOS else []
        if list(capitulo.brutos) != permitidos:
            brutos_fora.append(f"{arquivo.name}: {list(capitulo.brutos)} (esperado {permitidos})")
    return {"arquivos": len(arquivos), "iguais": len(arquivos) - len(diferentes),
            "diferentes": diferentes, "brutos_fora_do_esperado": brutos_fora}


def folhas_de_teste() -> list[Path]:
    return [CONTRATO / "Styles" / "livro.css", *sorted((CSS / "mapa_positivo").glob("*.css")),
            *sorted((CSS / "mapa_negativo").glob("*.css"))]


def css_byte_a_byte(pasta: Path) -> dict[str, Any]:
    """Cada folha como `Resource(kind=STYLESHEET)` vai ao EPUB do arnês e volta igual."""
    from caissa.core.model import Document, Resource, ResourceKind

    folhas = folhas_de_teste()
    copias = pasta / "folhas"
    copias.mkdir(parents=True, exist_ok=True)
    recursos = []
    for indice, folha in enumerate(folhas):
        copia = copias / f"{indice:02d}-{folha.parent.name}-{folha.name}"
        copia.write_bytes(folha.read_bytes())
        recursos.append(Resource(key=copia.name, kind=ResourceKind.STYLESHEET, path=str(copia),
                                 media_type="text/css"))
    documento = Document(resources=tuple(recursos))
    epub = montar_epub(pasta / "folhas.epub", [], documento, {})
    iguais = []
    with zipfile.ZipFile(epub) as pacote:
        for folha, recurso in zip(folhas, recursos, strict=True):
            dentro = pacote.read(f"OEBPS/Styles/{recurso.key}")
            iguais.append(dentro == folha.read_bytes())
    return {"folhas": len(folhas), "iguais": sum(iguais),
            "diferentes": [f.name for f, ok in zip(folhas, iguais, strict=True) if not ok]}


def mapa_de_estilo() -> dict[str, Any]:
    """As positivas com o estilo esperado e as negativas com o aviso esperado."""
    from caissa.editor.css.mapa_de_estilo import resolver

    contas = {"positivas": 0, "positivas_certas": 0, "negativas": 0, "negativas_certas": 0}
    erradas: list[str] = []
    for tipo, pasta in (("positivas", CSS / "mapa_positivo"), ("negativas", CSS / "mapa_negativo")):
        for folha in sorted(pasta.glob("*.css")):
            esperado = json.loads(folha.with_suffix(".json").read_text(encoding="utf-8"))
            obtido = resolver([(folha.name, folha.read_text(encoding="utf-8"))]).como_dict()
            contas[tipo] += 1
            certo = obtido == esperado and (tipo == "positivas") != bool(obtido["avisos"])
            contas[f"{tipo}_certas"] += certo
            if not certo:
                erradas.append(f"{tipo}/{folha.name}")
    return {**contas, "erradas": erradas}


def pasta_do_cb() -> Path:
    return _principal().parent / "Sigil-master" / "src" / "Resource_Files" / "python3lib"


def validar_no_cb(arquivos: Sequence[Path], imagens: Sequence[Path]) -> dict[str, Any]:
    """O CB validate nos arquivos, como um livro: os erros de contrato e os de conteúdo."""
    cb = pasta_do_cb()
    if str(cb) not in sys.path:
        sys.path.insert(0, str(cb))
    from sigil_chess.validate import validate_book

    documentos = [{"bookpath": f"Text/{p.name}", "text": p.read_text(encoding="utf-8")}
                  for p in arquivos]
    presentes = [d["bookpath"] for d in documentos]
    presentes += [f"Images/{p.name}" for p in imagens]
    presentes += [f"Styles/{p.name}" for p in sorted((CONTRATO / "Styles").glob("*.css"))]
    relatorio = validate_book(documentos, files=presentes).to_dict()
    erros = [i for i in relatorio["issues"] if i["severity"] == "error"]
    de_conteudo = [e for e in erros if e["message"] in ERROS_DE_CONTEUDO]
    de_contrato = [e for e in erros if e["message"] not in ERROS_DE_CONTEUDO]
    return {"arquivos": len(arquivos), "erros_de_contrato": len(de_contrato),
            "erros_de_conteudo": len(de_conteudo), "avisos": relatorio["warning_count"],
            "primeiros": [f"{e['bookpath']}:{e['line']} {e['message']}"
                          for e in de_contrato[:10]]}


MARCACOES_DO_CB = (("_MOVE_OPEN_RE", "cb-move"), ("_LINE_RE", "cb-line"),
                   ("_GAME_RE", "cb-game"), ("_DIAGRAM_RE", "cb-diagram"))
"""As marcações que o `validate.py` do CB acha por expressão, e a classe que cada uma tem de ter."""


def o_que_o_cb_confunde(documentos: Sequence[dict[str, str]]) -> dict[str, list[str]]:
    """O que a leitura do CB toma errado sem acusar (MARKUP §10); o portão exige nenhum.

    - ``confundidos``: o elemento que uma expressão do CB casa sem ter a classe dela (o hífen é
      fronteira de palavra: um `span.cb-move-x` seria lido como lance);
    - ``pulados``: o `cb-move` sem `data-fen`, que o CB pula como anterior ao contrato.

    O «0 erro» do CB não diz nada dos dois.
    """
    if str(pasta_do_cb()) not in sys.path:
        sys.path.insert(0, str(pasta_do_cb()))
    import sigil_chess.validate as cb

    confundidos = []
    for documento in documentos:
        for expressao, classe in MARCACOES_DO_CB:
            for casado in getattr(cb, expressao).finditer(documento["text"]):
                classes = cb._attributes(casado.group("attrs")).get("class", "").split()
                if classe not in classes:
                    confundidos.append(f"{documento['bookpath']}: «{' '.join(classes)}» lido "
                                       f"como {classe}")
    pulados = [f"{d['bookpath']}: {m.san} sem data-fen" for d in documentos
               for m in cb._moves_in(d["text"])
               if "cb-move" in m.attrs.get("class", "").split() and not m.attrs.get("data-fen")]
    return {"confundidos": confundidos, "pulados": pulados}


def montar_epub(destino: Path, capitulos: Sequence[tuple[str, str]], documento: Any,
                imagens: dict[str, bytes]) -> Path:
    """Um EPUB 3 mínimo com os capítulos legíveis, as folhas do projeto e as imagens.

    As folhas vêm do `folhas_do_livro` (o produto); o nome de cada uma é o do arquivo, e os
    capítulos as ligam por `../Styles/<nome>`.
    """
    from caissa.export.legivel import folhas_do_livro

    folhas = folhas_do_livro(documento)
    itens = [("nav", "nav.xhtml", "application/xhtml+xml", ' properties="nav"')]
    for indice, (nome, _) in enumerate(capitulos):
        itens.append((f"c{indice}", f"Text/{nome}", "application/xhtml+xml", ""))
    itens += [(f"css{i}", f"Styles/{nome}", "text/css", "") for i, (nome, _) in enumerate(folhas)]
    tipos = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
             ".jpeg": "image/jpeg", ".gif": "image/gif"}
    itens += [(f"img{i}", f"Images/{nome}", tipos.get(Path(nome).suffix.lower(),
                                                      "application/octet-stream"), "")
              for i, nome in enumerate(sorted(imagens))]
    manifesto = "\n".join(f'<item id="{i}" href="{h}" media-type="{m}"{p}/>'
                          for i, h, m, p in itens)
    espinha = "\n".join(f'<itemref idref="c{i}"/>' for i in range(len(capitulos)))
    idioma = documento.metadata.language or "pt-BR"
    opf = (f'<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf"'
           f' version="3.0" unique-identifier="uid" xml:lang="{idioma}">\n<metadata '
           'xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
           '<dc:identifier id="uid">urn:uuid:5f0a9b7e-4c1d-4e57-9d2a-caissa000h5</dc:identifier>\n'
           f"<dc:title>O portão do H5</dc:title>\n<dc:language>{idioma}</dc:language>\n"
           '<meta property="dcterms:modified">2026-09-30T00:00:00Z</meta>\n</metadata>\n'
           f"<manifest>\n{manifesto}\n</manifest>\n<spine>\n{espinha}\n</spine>\n</package>\n")
    ligacoes = "\n".join(f'<li><a href="Text/{nome}">{nome}</a></li>' for nome, _ in capitulos)
    ligacoes = ligacoes or '<li><a href="nav.xhtml">-</a></li>'
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html '
           'xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
           f'lang="{idioma}" xml:lang="{idioma}">\n<head><title>Sumário</title></head>\n<body>\n'
           f'<nav epub:type="toc" id="toc"><h1>Sumário</h1><ol>\n{ligacoes}\n'
           "</ol></nav>\n</body>\n</html>\n")
    container = ('<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" '
                 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n<rootfiles>\n'
                 '<rootfile full-path="OEBPS/content.opf" '
                 'media-type="application/oebps-package+xml"/>\n</rootfiles>\n</container>\n')
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as pacote:
        pacote.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                        compress_type=zipfile.ZIP_STORED)
        pacote.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        pacote.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        pacote.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        for nome, texto in capitulos:
            pacote.writestr(f"OEBPS/Text/{nome}", texto, compress_type=zipfile.ZIP_DEFLATED)
        for nome, dados in folhas:
            pacote.writestr(f"OEBPS/Styles/{nome}", dados, compress_type=zipfile.ZIP_DEFLATED)
        for nome, dados in sorted(imagens.items()):
            pacote.writestr(f"OEBPS/Images/{nome}", dados, compress_type=zipfile.ZIP_DEFLATED)
    return destino


def epub_do_ir_real(pasta_da_ida: Path, documentos: dict[str, Any], destino: Path) -> Path:
    """O EPUB do portão: os capítulos legíveis do IR real, a folha do contrato e as imagens."""
    from caissa.core.model import Document, Resource, ResourceKind

    capitulos = [(f"{nome}.xhtml", (pasta_da_ida / f"{nome}.xhtml").read_text(encoding="utf-8"))
                 for nome in documentos if (pasta_da_ida / f"{nome}.xhtml").is_file()]
    imagens = {p.name: p.read_bytes() for p in (pasta_da_ida / "Images").glob("*.svg")
               if any(p.name in texto for _, texto in capitulos)}
    for documento in documentos.values():
        for recurso in documento.resources:
            if recurso.kind is ResourceKind.IMAGE and recurso.path and Path(recurso.path).is_file():
                imagens[recurso.key] = Path(recurso.path).read_bytes()
    folha = CONTRATO / "Styles" / "livro.css"
    livro = Document(resources=(Resource(key="livro.css", kind=ResourceKind.STYLESHEET,
                                         path=str(folha), media_type="text/css"),))
    return montar_epub(destino, capitulos, livro, imagens)


def jar_do_epubcheck() -> Path | None:
    for base in (RAIZ, _principal()):
        achados = sorted((base / "tools").glob("epubcheck-*/epubcheck.jar"))
        if achados:
            return achados[-1]
    from caissa.export.epubcheck import find_epubcheck_jar

    return find_epubcheck_jar()


def epubcheck(epub: Path) -> dict[str, Any]:
    from caissa.export.epubcheck import run_epubcheck

    jar = jar_do_epubcheck()
    if jar is None:
        return {"erro": "o EPUBCheck não foi achado (tools/epubcheck-*/epubcheck.jar)"}
    try:
        medido = run_epubcheck(jar, epub)
    except OSError as falha:
        return {"erro": f"o Java não abriu: {falha}"}
    return {"jar": str(jar), "erros": medido.errors, "avisos": medido.warnings,
            "saida": medido.output[-3000:]}


# --------------------------------------------------------------------------- #
# As sabotagens
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def sabotagem(nome: str | None) -> Iterator[None]:
    """Troca uma peça do produto, só neste processo, pelo defeito que o portão tem de pegar."""
    from caissa.editor.css import mapa_de_estilo as mapa
    from caissa.export import legivel

    trocas: list[tuple[Any, str, Any]] = []

    def trocar(dono: Any, atributo: str, novo: Any) -> None:
        trocas.append((dono, atributo, getattr(dono, atributo)))
        setattr(dono, atributo, novo)

    if nome == "perde_fen":
        original = legivel.EscritorLegivel._bloco_diagram

        def sem_fen(self: Any, no: Any) -> str:
            return re.sub(r' data-fen="[^"]*"', "", original(self, no), count=1)

        trocar(legivel.EscritorLegivel, "_bloco_diagram", sem_fen)
    elif nome == "perde_classe":
        trocar(legivel, "_classe_do_estilo", lambda _nome: ())
    elif nome == "engole_desconhecido":
        # O leitor guarda o elemento fora do contrato pelo texto dele: sem o texto, o bruto
        # volta vazio e o escritor não escreve nada no lugar.
        trocar(legivel, "serializar_elemento", lambda _elemento: "")
    elif nome == "perde_atributo":
        trocar(legivel, "_preservados", lambda *_a, **_k: ())
    elif nome == "css_silencioso":
        resolver = mapa.resolver

        def sem_aviso(folhas: Any) -> Any:
            resultado = resolver(folhas)
            resultado.avisos.clear()
            return resultado

        trocar(mapa, "resolver", sem_aviso)
    elif nome == "nula":
        trocar(legivel.EscritorLegivel, "blocos", lambda _self, _blocos, **_kw: "")
    elif nome == "lance_sem_fen":
        # A forma do ciclo 1: o lance que não se joga num `cb-move` sem `data-fen`. A ida, a volta
        # e o validate do CB passam; só a conta do que o CB pula a pega.
        trocar(legivel, "CLASSE_LITERAL", "cb-move")
    try:
        yield
    finally:
        for dono, atributo, valor in reversed(trocas):
            setattr(dono, atributo, valor)


# --------------------------------------------------------------------------- #
# O portão
# --------------------------------------------------------------------------- #


def portao(saida: Path, *, ir_real: Path | None, nos: int, semente: int,
           sem_epubcheck: bool) -> tuple[dict[str, bool], dict[str, Any]]:
    """As seis exigências do H5, e o registro de tudo o que se mediu."""
    registro: dict[str, Any] = {"commit": _head(), "nos_do_corpus": nos, "semente": semente}
    exigencias: dict[str, bool] = {}
    pasta_da_ida = saida / "ida"

    idas: dict[str, Any] = {"sintetico": ida(corpus_sintetico(nos, semente), "sintetico",
                                             pasta_da_ida)}
    documentos = carregar_ir_real(ir_real) if ir_real is not None else {}
    for nome, documento in documentos.items():
        idas[nome] = ida(documento, nome, pasta_da_ida)
    registro["ida"] = idas
    faltam = [n for n, _, _ in LIVROS_REAIS if n not in documentos]
    total = sum(r["diferencas"] or 0 for r in idas.values())
    falhas = [n for n, r in idas.items() if r.get("erro") or r["diferencas"]
              or r.get("mapa_problemas") or r.get("n3") != r.get("n3_guardada")]
    contas = Counter()
    for r in idas.values():
        contas.update(r.get("normalizacoes", {}))
    guardadas = sum(r.get("n3_guardada") or 0 for r in idas.values())
    fora_do_lugar = sum(r.get("mapa_fora_do_lugar") or 0 for r in idas.values())
    exigencias[f"ida: {total} diferença(s) fora de N1–N4 em {len(idas)} documento(s) "
               f"(N1–N4 contadas: {dict(sorted(contas.items()))}; N3 guardada no mapa: "
               f"{guardadas} registro(s), "
               + (f"{fora_do_lugar} fora do lugar)" if fora_do_lugar else "todos no lugar)")
               + (f" -- sem o IR real de {', '.join(faltam)}" if faltam else "")
               + (f" -- {'; '.join(falhas)}" if falhas else "")] = not falhas and not faltam

    arquivos = arquivos_da_volta(pasta_da_ida)
    editados = sorted(EDITADOS.glob("*.xhtml"))
    resultado_da_volta = volta(arquivos)
    registro["volta"] = resultado_da_volta
    fora = resultado_da_volta["brutos_fora_do_esperado"]
    exigencias[f"volta: canon idêntico em {resultado_da_volta['iguais']}/"
               f"{resultado_da_volta['arquivos']} arquivos ({len(editados)} edições à mão), "
               f"{len(fora)} com bruto fora do esperado"
               + (f" -- {'; '.join(resultado_da_volta['diferentes'][:5])}"
                  if resultado_da_volta["diferentes"] else "")
               + (f" -- {'; '.join(fora[:3])}" if fora else "")] = (
        not resultado_da_volta["diferentes"] and not fora
        and len(editados) >= EDICOES_MINIMAS)

    folhas = css_byte_a_byte(saida)
    registro["css"] = folhas
    exigencias[f"CSS byte a byte: {folhas['iguais']}/{folhas['folhas']} folhas"] = (
        folhas["iguais"] == folhas["folhas"])

    mapa = mapa_de_estilo()
    registro["mapa_de_estilo"] = mapa
    exigencias[f"mapa de estilo: {mapa['positivas_certas']}/{mapa['positivas']} positivas e "
               f"{mapa['negativas_certas']}/{mapa['negativas']} negativas"
               + (f" -- {'; '.join(mapa['erradas'][:5])}" if mapa["erradas"] else "")] = (
        not mapa["erradas"] and mapa["positivas"] > 0 and mapa["negativas"] > 0)

    do_cb = [p for p in arquivos if p.parent != pasta_da_ida or p.stem in documentos]
    imagens = [*sorted((CONTRATO / "Images").glob("*")), *sorted((pasta_da_ida / "Images")
                                                               .glob("*"))]
    cb = validar_no_cb(do_cb, imagens)
    # O que o CB confunde sem acusar, no que o contrato e o escritor escrevem: as fixtures e os
    # arquivos da ida (o sintético também: o conteúdo sorteado não passa no validate, mas as
    # classes são as do escritor). As edições à mão ficam de fora: são da pessoa (a #09 digita um
    # lance sem a posição, que o leitor guarda bruto e o CB pula — o aviso é da validação, H10).
    escritos = [p for p in arquivos if p.parent != EDITADOS]
    confunde = o_que_o_cb_confunde([{"bookpath": f"Text/{p.name}",
                                     "text": p.read_text(encoding="utf-8")} for p in escritos])
    cb.update(confundidos=confunde["confundidos"][:10], n_confundidos=len(confunde["confundidos"]),
              pulados=confunde["pulados"][:10], n_pulados=len(confunde["pulados"]))
    registro["cb"] = cb
    exigencias[f"CB validate: {cb['erros_de_contrato']} erro(s) de contrato em {cb['arquivos']} "
               f"arquivos ({cb['erros_de_conteudo']} de conteúdo, {cb['avisos']} aviso(s)); nos "
               f"{len(escritos)} das fixtures e da ida, {cb['n_confundidos']} marcação(ões) que o "
               f"CB confunde e {cb['n_pulados']} lance(s) que ele pula por não ter data-fen"
               + (f" -- {'; '.join(cb['primeiros'][:5])}" if cb["primeiros"] else "")
               + (f" -- {'; '.join([*cb['confundidos'], *cb['pulados']][:5])}"
                  if cb["n_confundidos"] or cb["n_pulados"] else "")] = (
        cb["erros_de_contrato"] == 0 and not cb["n_confundidos"] and not cb["n_pulados"])

    if sem_epubcheck:
        registro["epubcheck"] = {"pulado": True}
    else:
        epub = epub_do_ir_real(pasta_da_ida, documentos, saida / "legivel.epub")
        medido = epubcheck(epub)
        registro["epubcheck"] = medido
        erros = medido.get("erros")
        exigencias[f"EPUBCheck: {erros if erros is not None else '?'} erro(s) no EPUB legível "
                   f"({len(documentos)} capítulo(s) do IR real)"
                   + (f" -- {medido['erro']}" if medido.get("erro") else "")] = (
            erros == 0 and bool(documentos))
    return exigencias, registro


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--ir-real", type=Path)
    parser.add_argument("--gerar-ir-real", type=Path)
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    parser.add_argument("--nos", type=int, default=NOS_DO_CORPUS)
    parser.add_argument("--semente", type=int, default=SEMENTE)
    parser.add_argument("--sem-epubcheck", action="store_true")
    args = parser.parse_args(argv)
    if args.gerar_ir_real is not None:
        for destino in gerar_ir_real(args.gerar_ir_real):
            print(f"o IR real gravado: {destino}")
        return 0
    if args.saida is None:
        parser.error("--saida é obrigatório (o portão grava só nela)")
    saida = args.saida if args.saida.is_absolute() else RAIZ / args.saida
    with sabotagem(args.sabotar):
        exigencias, registro = portao(saida, ir_real=args.ir_real, nos=args.nos,
                                      semente=args.semente, sem_epubcheck=args.sem_epubcheck)
    registro["sabotagem"] = args.sabotar
    registro["exigencias"] = exigencias
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "ida_e_volta.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


_ = tempfile  # a pasta temporária é a da linha de comando (`--saida`)

if __name__ == "__main__":
    raise SystemExit(main())
