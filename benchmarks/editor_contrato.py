r"""O contrato de marcação e a política de CSS, conferidos — o portão do passo H3.

`docs/MARKUP_CAISSA.md` é o contrato; as fixtures em `tests/fixtures/editor/` são a prova dele.
Este instrumento confere, sem implementar nada do que o H5 vai construir:

1. **A cobertura:** cada linha da S4 (`LINHAS_DO_S4`) tem a fixture dela, e o §11 do contrato
   nomeia a mesma — 100 %.
2. **O `CB validate`** (`..\Sigil-master\...\sigil_chess\validate.py`, no `sys.path` só aqui) sobre
   as fixtures do contrato e as combinações, com as imagens que o livro leva: **0 erro**.
3. **A fixture legada** (`legado_xhtml_builder.xhtml`, saída do exportador HTML de hoje, no perfil
   de máquina) é lida pelo leitor atual (`read_html_text`) e traz o título, o parágrafo, o
   diagrama e a partida.
4. **As fixtures do mapa de estilo:** cada `.css` tem o `.json` com o resultado esperado na forma do
   §9 do contrato; as positivas cobrem cada propriedade do mapa com dois valores e não avisam; as
   negativas avisam `css-fora-do-mapa` com seletor, propriedade, arquivo e linha.
5. **As fixtures douradas do sidecar** (spec Apêndice C) existem, assinadas pelo crítico no
   `LEIAME.md`, com o SHA-256 igual ao do relatório (§H3 do `EDITOR_HTML_CSS_REPORT.md`).

**Sabotagem** `--sabotar sem_fen`: a negativa `contrato_negativas/negativa_sem_fen.xhtml` (um
diagrama sem `data-fen`) entra no conjunto limpo; o CB acusa, e o portão reprova.

Uso::

    & $PY benchmarks\editor_contrato.py --saida benchmarks\reports\editor\h3\1
    & $PY benchmarks\editor_contrato.py --regerar-legada
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

FIXTURES = RAIZ / "tests" / "fixtures" / "editor"
CONTRATO = FIXTURES / "contrato"
NEGATIVAS = FIXTURES / "contrato_negativas"
CSS = FIXTURES / "css"
SIDECAR = FIXTURES / "sidecar"
DOCUMENTO = RAIZ / "docs" / "MARKUP_CAISSA.md"
RELATORIO = RAIZ / "docs" / "quality" / "EDITOR_HTML_CSS_REPORT.md"
SABOTAGENS = ("sem_fen",)

#: Cada linha da S4 (spec §5.2) e a fixture dela — a tabela do §11 do contrato.
LINHAS_DO_S4: dict[str, str] = {
    "Heading(level)": "titulo.xhtml",
    'Paragraph(style=None)': "paragrafo.xhtml",
    'Paragraph(style="Movetext")': "paragrafo_movetext.xhtml",
    'Paragraph(style="Caption"|"Footnote"|X)': "paragrafo_estilos.xhtml",
    "Emphasis…Subscript": "formatacao.xhtml",
    "RunProps.language": "lingua.xhtml",
    "Link/Anchor/NoteRef": "links_ancoras_notas.xhtml",
    "Diagram": "diagrama.xhtml",
    "GameScore/MoveNode/Move": "partida.xhtml",
    "PieceGlyph": "figurina.xhtml",
    "NagSymbol": "nag.xhtml",
    "página do PDF": "pagina.xhtml",
    "RawPassthrough/RawInline": "bruto.xhtml",
    "html_attributes": "atributos.xhtml",
}
COMBINACOES = ("combinacao_capitulo.xhtml", "combinacao_partida_com_diagrama.xhtml")
LEGADA = "legado_xhtml_builder.xhtml"
SIDECAR_DOURADAS = ("v2_completo.jsonl", "v1_de_hoje.jsonl", "v1_migrado_esperado.jsonl")
ASSINATURA = "escrito pelo crítico (Codex)"

#: As propriedades do mapa de estilo (§9 do contrato), cada uma com dois valores nas positivas.
PROPRIEDADES_DO_MAPA = (
    "font-family", "font-size", "font-weight", "font-style", "font-variant", "color",
    "background-color", "text-align", "text-indent", "margin-top", "margin-right",
    "margin-bottom", "margin-left", "line-height", "letter-spacing", "text-transform",
    "break-before", "widows", "orphans",
)
CAMPOS_DO_AVISO = ("codigo", "seletor", "propriedade", "arquivo", "linha")


def _principal() -> Path:
    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    return Path(comum).parent if comum else RAIZ


def pasta_do_cb() -> Path:
    """O `python3lib` do Sigil, onde mora o pacote `sigil_chess` (o CB)."""
    return _principal().parent / "Sigil-master" / "src" / "Resource_Files" / "python3lib"


# --------------------------------------------------------------------------- #
# As conferências
# --------------------------------------------------------------------------- #


def conferir_cobertura() -> list[str]:
    """Cada linha da S4 com a fixture, e o §11 do contrato nomeando a mesma."""
    faltas = [f"a linha «{linha}» da S4 não tem a fixture {nome}"
              for linha, nome in LINHAS_DO_S4.items() if not (CONTRATO / nome).is_file()]
    faltas += [f"a combinação {nome} não existe" for nome in COMBINACOES
               if not (CONTRATO / nome).is_file()]
    texto = DOCUMENTO.read_text(encoding="utf-8") if DOCUMENTO.is_file() else ""
    secao = texto.split("## 11.", 1)[-1] if "## 11." in texto else ""
    faltas += [f"o §11 do contrato não nomeia {nome}"
               for nome in (*LINHAS_DO_S4.values(), *COMBINACOES, LEGADA)
               if f"`{nome}`" not in secao]
    return faltas


def documentos_do_livro(nomes: list[Path]) -> tuple[list[dict[str, str]], list[str]]:
    """As fixtures como um livro do EPUB: `Text/<nome>`, com as imagens e a folha que ele leva."""
    documentos = [{"bookpath": f"Text/{p.name}", "text": p.read_text(encoding="utf-8")}
                  for p in nomes]
    arquivos = [d["bookpath"] for d in documentos]
    arquivos += [f"Images/{p.name}" for p in sorted((CONTRATO / "Images").glob("*.svg"))]
    arquivos += [f"Styles/{p.name}" for p in sorted((CONTRATO / "Styles").glob("*.css"))]
    return documentos, arquivos


def validar_no_cb(nomes: list[Path]) -> dict[str, Any]:
    cb = pasta_do_cb()
    if str(cb) not in sys.path:
        sys.path.insert(0, str(cb))
    from sigil_chess.validate import validate_book

    documentos, arquivos = documentos_do_livro(nomes)
    return validate_book(documentos, files=arquivos).to_dict()


def conferir_legada() -> list[str]:
    """O leitor de hoje lê a fixture legada e acha o título, o parágrafo, o diagrama e a partida."""
    from caissa.core.model import Diagram, Heading, Paragraph
    from caissa.core.model.visitor import walk
    from caissa.export.html import read_html_text

    arquivo = CONTRATO / LEGADA
    if not arquivo.is_file():
        return [f"a fixture legada {LEGADA} não existe (rode --regerar-legada)"]
    try:
        documento = read_html_text(arquivo.read_text(encoding="utf-8"))
    except Exception as falha:  # noqa: BLE001 - o leitor não pode derrubar o portão
        return [f"o leitor atual não lê a fixture legada: {type(falha).__name__}: {falha}"]
    tipos = {type(no).__name__ for _, no in walk(documento)}
    esperados = {Heading.__name__, Paragraph.__name__, Diagram.__name__, "GameScore"}
    return [f"a fixture legada relida não tem {nome}" for nome in sorted(esperados - tipos)]


def _aviso_valido(aviso: Any, arquivo: str) -> bool:
    return (isinstance(aviso, dict) and set(aviso) == set(CAMPOS_DO_AVISO)
            and aviso["codigo"] == "css-fora-do-mapa" and aviso["arquivo"] == arquivo
            and isinstance(aviso["seletor"], str) and aviso["seletor"]
            and isinstance(aviso["propriedade"], str)
            and type(aviso["linha"]) is int and aviso["linha"] >= 1)


def conferir_css() -> tuple[list[str], dict[str, int]]:
    """Cada fixture do mapa com o resultado declarado, na forma do §9 do contrato."""
    faltas: list[str] = []
    valores: dict[str, set[str]] = {p: set() for p in PROPRIEDADES_DO_MAPA}
    contagem = {"positivas": 0, "negativas": 0}
    for pasta, tipo in (("mapa_positivo", "positivas"), ("mapa_negativo", "negativas")):
        for folha in sorted((CSS / pasta).glob("*.css")):
            esperado_arquivo = folha.with_suffix(".json")
            if not esperado_arquivo.is_file():
                faltas.append(f"{pasta}/{folha.name} sem o resultado esperado (.json)")
                continue
            esperado = json.loads(esperado_arquivo.read_text(encoding="utf-8"))
            estilos, avisos = esperado.get("estilos"), esperado.get("avisos")
            if not (isinstance(estilos, dict) and isinstance(avisos, list)
                    and set(esperado) == {"estilos", "avisos"}
                    and all(isinstance(v, dict) and all(isinstance(x, str) for x in v.values())
                            for v in estilos.values())):
                faltas.append(f"{pasta}/{esperado_arquivo.name} fora da forma do §9")
                continue
            if not all(_aviso_valido(a, folha.name) for a in avisos):
                faltas.append(f"{pasta}/{esperado_arquivo.name}: aviso fora da forma do §9")
            if tipo == "positivas" and avisos:
                faltas.append(f"{pasta}/{folha.name}: a positiva declara aviso")
            if tipo == "negativas" and not avisos:
                faltas.append(f"{pasta}/{folha.name}: a negativa não declara aviso")
            contagem[tipo] += 1
            if tipo == "positivas":
                for estilo in estilos.values():
                    for propriedade, valor in estilo.items():
                        if propriedade in valores:
                            valores[propriedade].add(valor)
    faltas += [f"a propriedade {p} do mapa tem {len(v)} valor(es) nas positivas (mínimo 2)"
               for p, v in valores.items() if len(v) < 2]
    return faltas, contagem


def _hashes_do_relatorio() -> dict[str, str]:
    """Os SHA-256 que o relatório do H3 registrou: `` `nome.jsonl` `` e o hash na mesma linha."""
    if not RELATORIO.is_file():
        return {}
    texto = RELATORIO.read_text(encoding="utf-8")
    secao = texto.split("## H3", 1)[-1].split("\n## ", 1)[0] if "## H3" in texto else ""
    achados = {}
    for nome in SIDECAR_DOURADAS:
        casado = re.search(rf"`{re.escape(nome)}`[^\n]*?`([0-9a-f]{{64}})`", secao)
        if casado:
            achados[nome] = casado.group(1)
    return achados


def conferir_sidecar() -> tuple[list[str], dict[str, str]]:
    faltas: list[str] = []
    hashes: dict[str, str] = {}
    for nome in SIDECAR_DOURADAS:
        arquivo = SIDECAR / nome
        if not arquivo.is_file():
            faltas.append(f"a fixture dourada do sidecar {nome} não existe")
            continue
        hashes[nome] = hashlib.sha256(arquivo.read_bytes()).hexdigest()
    leiame = SIDECAR / "LEIAME.md"
    if not leiame.is_file() or ASSINATURA not in leiame.read_text(encoding="utf-8"):
        faltas.append("as fixtures do sidecar não estão assinadas pelo crítico (LEIAME.md)")
    registrados = _hashes_do_relatorio()
    for nome, valor in hashes.items():
        if registrados.get(nome) != valor:
            faltas.append(f"o SHA-256 de {nome} ({valor[:12]}…) não é o do relatório do H3 "
                          f"({(registrados.get(nome) or 'ausente')[:12]})")
    return faltas, hashes


# --------------------------------------------------------------------------- #
# A fixture legada
# --------------------------------------------------------------------------- #


def regerar_legada() -> Path:
    """A fixture legada: um documento pequeno pelo exportador HTML de hoje (perfil de máquina)."""
    import tempfile

    from caissa.core.model import Diagram, Document, Heading, Paragraph, Text
    from caissa.export import export
    from caissa.export.base import ExportOptions
    from caissa.export.text import game_from_pgn

    partida = game_from_pgn('[White "Carlsen"]\n[Black "Caruana"]\n[Result "1-0"]\n\n'
                            "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0\n")
    documento = Document(body=(
        Heading(level=1, content=(Text(content="Capítulo legado"),)),
        Paragraph(content=(Text(content="Um parágrafo do perfil de máquina."),)),
        Diagram(fen="6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", stipulation="Mate em 1"),
        partida,
    ))
    with tempfile.TemporaryDirectory() as pasta:
        destino = Path(pasta) / "legado.xhtml"
        export(documento, destino, "html", options=ExportOptions(embed_ir=False))
        texto = destino.read_text(encoding="utf-8")
    alvo = CONTRATO / LEGADA
    alvo.write_text(texto, encoding="utf-8", newline="\n")
    return alvo


# --------------------------------------------------------------------------- #
# O portão
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    parser.add_argument("--regerar-legada", action="store_true")
    args = parser.parse_args(argv)
    if args.regerar_legada:
        print(f"a fixture legada regravada: {regerar_legada()}")
        return 0

    exigencias: dict[str, bool] = {}
    cobertura = conferir_cobertura()
    exigencias["cobertura: 100 % das linhas da S4 com fixture, e o §11 com as mesmas"
               + ("" if not cobertura else " -- " + "; ".join(cobertura))] = not cobertura

    limpas = [CONTRATO / n for n in (*LINHAS_DO_S4.values(), *COMBINACOES)
              if (CONTRATO / n).is_file()]
    if args.sabotar == "sem_fen":
        limpas.append(NEGATIVAS / "negativa_sem_fen.xhtml")
    relatorio_cb = validar_no_cb(limpas)
    erros = [i for i in relatorio_cb["issues"] if i["severity"] == "error"]
    exigencias[f"CB validate: {relatorio_cb['error_count']} erro(s) em {len(limpas)} fixtures "
               f"({relatorio_cb['warning_count']} aviso(s))"
               + ("" if not erros else " -- " + "; ".join(
                   f"{e['bookpath']}:{e['line']} {e['message']}" for e in erros[:5]))] = (
        not erros)

    legada = conferir_legada()
    exigencias["a fixture legada lida pelo leitor atual"
               + ("" if not legada else " -- " + "; ".join(legada))] = not legada

    css, contagem = conferir_css()
    exigencias[f"mapa de estilo: {contagem['positivas']} positivas e {contagem['negativas']} "
               "negativas com o resultado declarado"
               + ("" if not css else " -- " + "; ".join(css[:5]))] = not css

    sidecar, hashes = conferir_sidecar()
    exigencias["sidecar: as três fixtures douradas do crítico, com o SHA-256 do relatório"
               + ("" if not sidecar else " -- " + "; ".join(sidecar))] = not sidecar

    registro = {"sabotagem": args.sabotar, "exigencias": exigencias, "cb": relatorio_cb,
                "sidecar_sha256": hashes, "css": contagem, "cb_em": str(pasta_do_cb())}
    if args.saida is not None:
        args.saida.mkdir(parents=True, exist_ok=True)
        (args.saida / "contrato.json").write_text(
            json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
        metricas = {"linhas_do_s4": len(LINHAS_DO_S4),
                    "linhas_cobertas": sum((CONTRATO / n).is_file() for n in LINHAS_DO_S4.values()),
                    "erros_do_cb": relatorio_cb["error_count"],
                    "avisos_do_cb": relatorio_cb["warning_count"],
                    "fixtures_de_css": contagem["positivas"] + contagem["negativas"]}
        (args.saida / "metricas.json").write_text(json.dumps(metricas, indent=1),
                                                  encoding="utf-8")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
