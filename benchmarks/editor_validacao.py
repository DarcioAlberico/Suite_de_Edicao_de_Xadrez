r"""A validação em camadas, conferida — o portão do passo H10 do Editor HTML/CSS.

1. **Os defeitos** (`tests/fixtures/editor/defeitos/`, um arquivo por regra, e o `seg-tamanho`
   de 8 MB montado aqui): cada um dá **exatamente** os problemas do `esperado.json` — o código e
   a linha:coluna, tirados de um marcador no texto pela definição da regra. E toda regra
   registrada (menos as do EPUBCheck, item 3) tem o seu defeito. **100 %.**
2. **O limpo**: nenhum problema que bloqueia ou avisa nas fixtures do contrato (as 14 linhas da
   S4 e as 2 combinações) e nos capítulos legíveis do IR real (`LIVRO` p. 31–38, `KEMERI` p. 80,
   `PEDIDO` p. 50–60, `DEM` p. 20–25, o do H5: `--ir-real`), com as folhas e as imagens deles.
   As notas (`informa`) são contadas à parte; as dúvidas do OCR do IR real também (são dúvidas
   de verdade). **0 falso positivo.**
3. **O EPUBCheck** (`--json`): o EPUB mínimo limpo dá 0 erro (o controle); com um erro injetado
   — a etiqueta errada e a imagem que falta —, toda mensagem de erro volta com o local no
   arquivo injetado. **100 %.**
4. **O desempenho**: a validação inteira (todas as camadas, o contraste também) de um arquivo de
   260 KB, a mediana de 5, **≤ 500 ms** (spec §5.5). Mede tempo: roda com a máquina livre.

**Sabotagens**, cada uma tem de reprovar: `sem_linha` (o local perde a linha e a coluna) e
`regra_muda` (a regra do diagrama sem `data-fen` desligada).

Uso::

    & $PY benchmarks\editor_validacao.py --ir-real benchmarks\reports\editor\h5_ir_real `
        --saida benchmarks\reports\editor\h10
    & $PY benchmarks\editor_validacao.py --sabotar sem_linha --saida <pasta>
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import json
import statistics
import sys
import tempfile
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
for _caminho in (RAIZ / "src", RAIZ / "benchmarks"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

DEFEITOS = RAIZ / "tests" / "fixtures" / "editor" / "defeitos"
CONTRATO = RAIZ / "tests" / "fixtures" / "editor" / "contrato"
ORCAMENTO_MS = 500.0
ALVO_BYTES = 260 * 1024
REPETICOES = 5
SABOTAGENS = ("sem_linha", "regra_muda")
NAO_CONTAM = ("informa",)
"""As notas não são falso positivo: dizem o que vale saber (o DOCX não leva, a prévia não
desenha)."""


def arquivos_da_pasta(pasta: Path) -> dict[str, bytes]:
    """Os arquivos de um livro (`Text/`, `Styles/`, `Images/`) pelo caminho relativo."""
    return {p.relative_to(pasta).as_posix(): p.read_bytes() for p in sorted(pasta.rglob("*"))
            if p.is_file() and p.parent != pasta and p.suffix != ".pyc"}


def _contexto(arquivos: dict[str, bytes], dados: dict[str, Any]) -> Any:
    from caissa.editor.leitura import mapa_de_json
    from caissa.editor.validacao import Contexto

    return Contexto(
        arquivos=arquivos,
        glossario=frozenset(dados["glossario"]) if "glossario" in dados else None,
        fontes=dados.get("fontes", {}),
        mapa=mapa_de_json(json.loads(arquivos[dados["mapa"]])) if "mapa" in dados else None)


def _chaves(problemas: list[Any]) -> collections.Counter[tuple[str, int, int]]:
    return collections.Counter((p.codigo, p.local.linha, p.local.coluna) for p in problemas)


def _xhtml(corpo: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR" xml:lang="pt-BR">\n'
            f"<head><title>t</title></head>\n<body>\n{corpo}\n</body>\n</html>\n")


# --------------------------------------------------------------------------- #
# 1. Os defeitos
# --------------------------------------------------------------------------- #


def defeitos() -> tuple[dict[str, bool], dict[str, Any]]:
    from caissa.editor.validacao import REGRAS, Contexto, validar_arquivo
    from caissa.editor.validacao.xml import LIMITE_DE_BYTES

    esperado = json.loads((DEFEITOS / "esperado.json").read_text(encoding="utf-8"))
    arquivos = arquivos_da_pasta(DEFEITOS)
    certos, errados = [], []
    for nome, dados in esperado["defeitos"].items():
        obtidos = validar_arquivo(nome, arquivos[nome].decode("utf-8"),
                                  _contexto(arquivos, dados["contexto"]))
        quer = collections.Counter((e["codigo"], e["linha"], e["coluna"])
                                   for e in dados["problemas"])
        (certos if _chaves(obtidos) == quer else errados).append(
            nome if _chaves(obtidos) == quer else
            f"{nome}: esperado {sorted(quer)}, obtido {[str(p) for p in obtidos][:4]}")
    # O de 8 MB é montado aqui: não vai para o repositório.
    enorme = _xhtml("<p>" + "x" * (LIMITE_DE_BYTES + 1) + "</p>")
    for nome, dados in esperado["gerados"].items():
        obtidos = validar_arquivo(f"Text/{nome}.xhtml", enorme, Contexto())
        quer = collections.Counter((e["codigo"], e["linha"], e["coluna"])
                                   for e in dados["problemas"])
        (certos if _chaves(obtidos) == quer else errados).append(
            f"(gerado) {nome}" if _chaves(obtidos) == quer else
            f"(gerado) {nome}: obtido {[str(p) for p in obtidos][:4]}")
    cobertas = {d["regra"] for d in esperado["defeitos"].values()} | {
        d["regra"] for d in esperado["gerados"].values()}
    faltam = sorted(c for c in REGRAS if not c.startswith("epubcheck-") and c not in cobertas)
    total = len(esperado["defeitos"]) + len(esperado["gerados"])
    exigencias = {
        f"defeitos: {len(certos)}/{total} com o código e a linha:coluna certos "
        f"({len(cobertas)} regras com defeito"
        + (f"; sem defeito: {', '.join(faltam)}" if faltam else "") + ")"
        + (f" -- {'; '.join(errados[:3])}" if errados else ""): (
            not errados and not faltam and len(certos) == total),
    }
    return exigencias, {"certos": certos, "errados": errados, "regras_sem_defeito": faltam}


# --------------------------------------------------------------------------- #
# 2. O limpo
# --------------------------------------------------------------------------- #


def _projeto_do_ir(nome: str, documento: Any) -> tuple[dict[str, bytes], Any]:
    """O capítulo legível do IR real como projeto: o XHTML, as folhas, as imagens e o mapa."""
    from caissa.export.legivel import Capitulo, escrever_capitulo, folhas_do_livro

    folhas = folhas_do_livro(documento)
    capitulo = Capitulo(blocos=documento.body, titulo=nome,
                        folhas=tuple(f"../Styles/{f}" for f, _ in folhas),
                        idioma=documento.metadata.language or "pt-BR")
    texto, escritor = escrever_capitulo(capitulo, documento)
    arquivos = {f"Text/{nome}.xhtml": texto.encode("utf-8")}
    arquivos |= {f"Styles/{f}": dados for f, dados in folhas}
    arquivos |= {f"Images/{f}": svg.encode("utf-8") for f, svg in escritor.imagens.items() if svg}
    return arquivos, escritor.mapa


def limpo(ir_real: Path | None) -> tuple[dict[str, bool], dict[str, Any]]:
    import editor_contrato
    from editor_ida_e_volta import LIVROS_REAIS, carregar_ir_real

    from caissa.editor.validacao import Contexto, validar_arquivo, validar_projeto

    falsos: list[str] = []
    notas: collections.Counter[str] = collections.Counter()
    duvidas = 0
    arquivos_validados = 0
    contrato = arquivos_da_pasta(CONTRATO) | {
        f"Text/{n}": (CONTRATO / n).read_bytes()
        for n in (*editor_contrato.LINHAS_DO_S4.values(), *editor_contrato.COMBINACOES)}
    for nome in (*editor_contrato.LINHAS_DO_S4.values(), *editor_contrato.COMBINACOES):
        arquivos_validados += 1
        for problema in validar_arquivo(f"Text/{nome}", contrato[f"Text/{nome}"].decode("utf-8"),
                                        Contexto(arquivos=contrato)):
            if problema.severidade in NAO_CONTAM:
                notas[problema.codigo] += 1
            else:
                falsos.append(str(problema))
    documentos = carregar_ir_real(ir_real) if ir_real is not None else {}
    for nome, documento in documentos.items():
        arquivos, mapa = _projeto_do_ir(nome, documento)
        for problemas in validar_projeto(Contexto(arquivos=arquivos, mapa=mapa)).values():
            arquivos_validados += 1
            for problema in problemas:
                if problema.codigo == "ocr-duvida-pendente":
                    duvidas += 1
                elif problema.severidade in NAO_CONTAM:
                    notas[problema.codigo] += 1
                else:
                    falsos.append(str(problema))
    faltam = [n for n, _, _ in LIVROS_REAIS if n not in documentos]
    exigencias = {
        f"limpo: {len(falsos)} problema(s) que bloqueiam ou avisam em {arquivos_validados} "
        f"arquivos ({len(notas)} tipo(s) de nota, {sum(notas.values())} nota(s); "
        f"{duvidas} dúvida(s) do OCR pendente(s))"
        + (f" -- sem o IR real de {', '.join(faltam)}" if faltam else "")
        + (f" -- {'; '.join(falsos[:3])}" if falsos else ""): not falsos and not faltam,
    }
    return exigencias, {"falsos_positivos": falsos, "notas": dict(notas), "duvidas": duvidas,
                        "livros": sorted(documentos)}


# --------------------------------------------------------------------------- #
# 3. O EPUBCheck
# --------------------------------------------------------------------------- #

_OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="id">urn:uuid:12345678-1234-4234-8234-123456789012</dc:identifier>
<dc:title>O livro do portão</dc:title>
<dc:language>pt-BR</dc:language>
<meta property="dcterms:modified">2026-09-30T00:00:00Z</meta>
</metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="c1" href="Text/cap1.xhtml" media-type="application/xhtml+xml"/>
</manifest>
<spine><itemref idref="c1"/></spine>
</package>
"""
_NAV = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"
      lang="pt-BR" xml:lang="pt-BR">
<head><title>Sumário</title></head>
<body><nav epub:type="toc"><ol><li><a href="Text/cap1.xhtml">O capítulo</a></li></ol></nav></body>
</html>
"""
INJECOES = {
    "limpo": "<p>Um parágrafo.</p>",
    "etiqueta_errada": "<p>Um parágrafo que fecha errado.</span>",
    "imagem_que_falta": '<p><img src="../Images/falta.png" alt="Uma imagem que falta"/></p>',
}
"""O capítulo do EPUB mínimo: limpo (o controle) e com cada erro injetado."""


def _epub(destino: Path, corpo: str) -> Path:
    with zipfile.ZipFile(destino, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        epub.writestr("META-INF/container.xml", (
            '<?xml version="1.0" encoding="UTF-8"?>\n<container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile '
            'full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>"), compress_type=zipfile.ZIP_DEFLATED)
        epub.writestr("OEBPS/content.opf", _OPF, compress_type=zipfile.ZIP_DEFLATED)
        epub.writestr("OEBPS/nav.xhtml", _NAV, compress_type=zipfile.ZIP_DEFLATED)
        epub.writestr("OEBPS/Text/cap1.xhtml", _xhtml(corpo), compress_type=zipfile.ZIP_DEFLATED)
    return destino


def _jar() -> Path | None:
    from caissa.export.epubcheck import find_epubcheck_jar

    achado = find_epubcheck_jar()
    if achado is not None:
        return achado
    from editor_contrato import _principal

    return next(iter(sorted(_principal().glob("tools/epubcheck-*/epubcheck.jar"), reverse=True)),
                None)


LINHA_INJETADA = 6
"""A linha do corpo no capítulo mínimo (`_xhtml`): a declaração, o DOCTYPE, o html, o head e o
body vêm antes."""


def epubcheck() -> tuple[dict[str, bool], dict[str, Any]]:
    """O controle limpo, e cada erro injetado acusado no local injetado, com o local preservado.

    O EPUBCheck dá algumas mensagens sem local (a que segue um erro fatal): essas não entram na
    conta do local preservado, e ficam contadas à parte.
    """
    from caissa.editor.validacao.epubcheck import problemas_das_mensagens
    from caissa.export.epubcheck import run_epubcheck_json

    jar = _jar()
    if jar is None:
        return {"EPUBCheck: sem o epubcheck.jar nesta máquina": False}, {}
    registro: dict[str, Any] = {"jar": str(jar)}
    with tempfile.TemporaryDirectory(prefix="caissa_h10_epub_") as pasta:
        for nome, corpo in INJECOES.items():
            mensagens = run_epubcheck_json(jar, _epub(Path(pasta) / f"{nome}.epub", corpo))
            problemas = problemas_das_mensagens(mensagens)
            com_local = [(m, p) for m, p in zip(mensagens, problemas, strict=True)
                         if m.line >= 1]
            registro[nome] = {
                "erros": [str(p) for p in problemas if p.severidade == "bloqueia"],
                "no_local_injetado": sum(1 for p in problemas if p.severidade == "bloqueia"
                                         and p.local.arquivo == "Text/cap1.xhtml"
                                         and p.local.linha == LINHA_INJETADA),
                "com_local": len(com_local),
                "local_preservado": sum(1 for m, p in com_local
                                        if (p.local.linha, p.local.coluna) == (m.line, m.column)),
                "sem_local_no_epubcheck": len(mensagens) - len(com_local)}
    injetados = [registro[n] for n in INJECOES if n != "limpo"]
    acusados = sum(1 for r in injetados if r["no_local_injetado"])
    preservados = sum(r["local_preservado"] for r in injetados)
    com_local = sum(r["com_local"] for r in injetados)
    sem_local = sum(r["sem_local_no_epubcheck"] for r in injetados)
    exigencias = {
        f"EPUBCheck: o EPUB limpo com {len(registro['limpo']['erros'])} erro(s); "
        f"{acusados}/{len(injetados)} erros injetados acusados na linha injetada; "
        f"{preservados}/{com_local} locais do EPUBCheck preservados ({sem_local} mensagem(ns) "
        "que ele dá sem local)"
        + (f" -- {registro['limpo']['erros'][:2]}" if registro["limpo"]["erros"] else ""): (
            not registro["limpo"]["erros"] and acusados == len(injetados)
            and com_local > 0 and preservados == com_local),
    }
    return exigencias, registro


# --------------------------------------------------------------------------- #
# 4. O desempenho
# --------------------------------------------------------------------------- #


def _texto_de_260kb(ir_real: Path | None) -> tuple[str, dict[str, bytes], str]:
    """O arquivo de 260 KB: o capítulo repetido até o tamanho.

    O do PEDIDO p. 50–60 (o do H1), ou o do corpus sintético sem o IR real.
    """
    from editor_ida_e_volta import carregar_ir_real, corpus_sintetico

    documentos = carregar_ir_real(ir_real) if ir_real is not None else {}
    if "pedido" in documentos:
        arquivos, _ = _projeto_do_ir("pedido", documentos["pedido"])
        origem = "o capítulo legível do PEDIDO p. 50–60"
    else:
        arquivos, _ = _projeto_do_ir("sintetico", corpus_sintetico(2000, 42))
        origem = "o capítulo legível do corpus sintético (sem o IR real)"
    nome = next(n for n in arquivos if n.startswith("Text/"))
    texto = arquivos[nome].decode("utf-8")
    inicio, fim = texto.index("<body>") + len("<body>"), texto.rindex("</body>")
    corpo = texto[inicio:fim]
    vezes = max(1, -(-ALVO_BYTES // max(len(corpo.encode("utf-8")), 1)))
    texto = texto[:inicio] + corpo * vezes + texto[fim:]
    arquivos[nome] = texto.encode("utf-8")
    return nome, arquivos, origem


def desempenho(ir_real: Path | None) -> tuple[dict[str, bool], dict[str, Any]]:
    from caissa.editor.validacao import Contexto, validar_arquivo

    nome, arquivos, origem = _texto_de_260kb(ir_real)
    texto = arquivos[nome].decode("utf-8")
    contexto = Contexto(arquivos=arquivos)
    validar_arquivo(nome, texto, contexto)  # o aquecimento: os imports e o MuPDF
    tempos = []
    for _ in range(REPETICOES):
        inicio = time.perf_counter()
        validar_arquivo(nome, texto, contexto)
        tempos.append(1000 * (time.perf_counter() - inicio))
    mediana = statistics.median(tempos)
    kb = len(texto.encode("utf-8")) / 1024
    exigencias = {
        f"desempenho: {mediana:.0f} ms (a mediana de {REPETICOES}) num arquivo de {kb:.0f} KB "
        f"({origem}) ≤ {ORCAMENTO_MS:.0f} ms": mediana <= ORCAMENTO_MS and kb >= 250,
    }
    return exigencias, {"tempos_ms": tempos, "mediana_ms": mediana, "kb": kb, "origem": origem}


# --------------------------------------------------------------------------- #
# As sabotagens e a linha de comando
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def sabotagem(nome: str | None) -> Iterator[None]:
    from caissa.editor.validacao import contrato, folha, xml
    from caissa.editor.validacao.problema import Local

    trocas: list[tuple[Any, str, Any]] = []

    def trocar(dono: Any, atributo: str, novo: Any) -> None:
        trocas.append((dono, atributo, getattr(dono, atributo)))
        setattr(dono, atributo, novo)

    if nome == "sem_linha":
        trocar(xml.Documento, "local", lambda self, _no, _d=0: Local(self.arquivo, 1, 1))
        trocar(folha.Folha, "local", lambda self, _no: Local(self.arquivo, 1, 1))
    elif nome == "regra_muda":
        original = contrato._diagrama

        def sem_a_regra(documento: Any, figura: Any) -> list[Any]:
            return [p for p in original(documento, figura)
                    if p.codigo != "contrato-diagrama-sem-fen"]

        trocar(contrato, "_diagrama", sem_a_regra)
    try:
        yield
    finally:
        for dono, atributo, valor in reversed(trocas):
            setattr(dono, atributo, valor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--ir-real", type=Path)
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    parser.add_argument("--sem-desempenho", action="store_true",
                        help="não mede o tempo (a rodada com outra sessão medindo)")
    args = parser.parse_args(argv)
    saida = args.saida if args.saida.is_absolute() else RAIZ / args.saida
    ir_real = args.ir_real if args.ir_real is None or args.ir_real.is_absolute() \
        else RAIZ / args.ir_real
    exigencias: dict[str, bool] = {}
    registro: dict[str, Any] = {"sabotagem": args.sabotar}
    with sabotagem(args.sabotar):
        for rotulo, medir in (("defeitos", defeitos), ("limpo", lambda: limpo(ir_real)),
                              ("epubcheck", epubcheck)):
            parte, dados = medir()
            exigencias |= parte
            registro[rotulo] = dados
        if not args.sem_desempenho:
            parte, dados = desempenho(ir_real)
            exigencias |= parte
            registro["desempenho"] = dados
    registro["exigencias"] = exigencias
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "validacao.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
