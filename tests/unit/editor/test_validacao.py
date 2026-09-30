"""A validação em camadas (Editor HTML/CSS, H10): cada regra acusa o seu defeito, no lugar certo.

O portão inteiro (o IR real limpo, o EPUBCheck, o tempo) é o `benchmarks/editor_validacao.py`;
aqui, o que roda sem Java e sem a máquina livre: os defeitos um a um, o limpo do contrato, os
consertos, as colunas, o local do EPUBCheck e a fronteira sem Qt.
"""

from __future__ import annotations

import ast
import collections
import json
import subprocess
import sys
from pathlib import Path

import pytest

from caissa.editor.leitura import mapa_de_json
from caissa.editor.previa import paginar, resolver_variaveis
from caissa.editor.validacao import REGRAS, Contexto, validar_arquivo
from caissa.editor.validacao import epubcheck as camada_do_epubcheck
from caissa.editor.validacao.xml import LIMITE_DE_BYTES, ler
from caissa.export.epubcheck import EpubCheckMessage

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "benchmarks"))
import editor_contrato  # noqa: E402

DEFEITOS = RAIZ / "tests" / "fixtures" / "editor" / "defeitos"
CONTRATO = RAIZ / "tests" / "fixtures" / "editor" / "contrato"
ESPERADO = json.loads((DEFEITOS / "esperado.json").read_text(encoding="utf-8"))


def _arquivos(pasta: Path) -> dict[str, bytes]:
    return {p.relative_to(pasta).as_posix(): p.read_bytes() for p in sorted(pasta.rglob("*"))
            if p.is_file() and p.parent != pasta}


ARQUIVOS = _arquivos(DEFEITOS)


def _contexto(dados: dict) -> Contexto:
    return Contexto(
        arquivos=ARQUIVOS,
        glossario=frozenset(dados["glossario"]) if "glossario" in dados else None,
        fontes=dados.get("fontes", {}),
        mapa=mapa_de_json(json.loads(ARQUIVOS[dados["mapa"]])) if "mapa" in dados else None)


def _chaves(problemas: list) -> collections.Counter:
    return collections.Counter((p.codigo, p.local.linha, p.local.coluna) for p in problemas)


@pytest.mark.parametrize("nome", sorted(ESPERADO["defeitos"]))
def test_cada_defeito_da_exatamente_o_esperado(nome: str) -> None:
    dados = ESPERADO["defeitos"][nome]
    obtidos = validar_arquivo(nome, ARQUIVOS[nome].decode("utf-8"), _contexto(dados["contexto"]))
    esperados = collections.Counter((e["codigo"], e["linha"], e["coluna"])
                                    for e in dados["problemas"])
    assert _chaves(obtidos) == esperados, [str(p) for p in obtidos]


def test_toda_regra_tem_o_seu_defeito() -> None:
    cobertas = {d["regra"] for d in ESPERADO["defeitos"].values()}
    cobertas |= {d["regra"] for d in ESPERADO["gerados"].values()}
    faltam = {c for c in REGRAS if not c.startswith("epubcheck-")} - cobertas
    assert not faltam
    assert len(ESPERADO["defeitos"]) + len(ESPERADO["gerados"]) >= 40


def test_o_vocabulario_do_validador_e_o_do_contrato() -> None:
    """Toda classe `cb-*` que o MARKUP nomeia o validador conhece, e só elas (§12.4)."""
    import re

    from caissa.editor.validacao.contrato import CLASSES

    texto = (RAIZ / "docs" / "MARKUP_CAISSA.md").read_text(encoding="utf-8")
    nomeadas = set(re.findall(r"cb-[a-z0-9]+(?:-[a-z0-9]+)*", texto))
    # As famílias, os exemplos de nome errado do §10 e o exemplo de estilo do §4.
    fora = {n for n in nomeadas if n.startswith(("cb-style", "cb-depth"))}
    fora |= {"cb-move-context", "cb-move-x"}
    assert nomeadas - fora == CLASSES


def test_o_arquivo_de_8_mb_nem_se_le() -> None:
    texto = "<html><body><p>" + "x" * (LIMITE_DE_BYTES + 1) + "</p></body></html>"
    problemas = validar_arquivo("Text/enorme.xhtml", texto)
    assert [(p.codigo, p.local.linha, p.local.coluna) for p in problemas] == [
        ("seg-tamanho", 1, 1)]


def test_as_fixtures_do_contrato_nao_acusam_nada_que_bloqueie_ou_avise() -> None:
    arquivos = _arquivos(CONTRATO) | {f"Text/{n}": (CONTRATO / n).read_bytes() for n in (
        *editor_contrato.LINHAS_DO_S4.values(), *editor_contrato.COMBINACOES)}
    for nome in (*editor_contrato.LINHAS_DO_S4.values(), *editor_contrato.COMBINACOES):
        problemas = validar_arquivo(f"Text/{nome}", arquivos[f"Text/{nome}"].decode("utf-8"),
                                    Contexto(arquivos=arquivos))
        assert [str(p) for p in problemas if p.severidade != "informa"] == [], nome


@pytest.mark.parametrize("codigo", ["a11y-lang", "a11y-abreviatura"])
def test_o_conserto_seguro_tira_o_problema(codigo: str) -> None:
    nome = f"Text/{codigo}.xhtml"
    texto = ARQUIVOS[nome].decode("utf-8")
    problema = next(p for p in validar_arquivo(nome, texto, Contexto(arquivos=ARQUIVOS))
                    if p.codigo == codigo)
    assert problema.conserto is not None
    consertado = problema.conserto.aplicar(texto)
    depois = validar_arquivo(nome, consertado, Contexto(arquivos=ARQUIVOS))
    assert codigo not in {p.codigo for p in depois}
    assert "xml-mal-formado" not in {p.codigo for p in depois}


def test_a_coluna_conta_caracteres_e_nao_bytes() -> None:
    documento, problemas = ler("t.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml">'
                                          "<p>çãõ<b>x</b></p>\n  <i>y</i></html>")
    assert problemas == []
    posicoes = {e.nome: (e.linha, e.coluna) for e in documento.elementos()}
    assert posicoes["b"] == (1, 50)
    assert posicoes["i"] == (2, 3)


def test_o_local_do_epubcheck_passa_inteiro_e_a_falta_dele_fica_dita() -> None:
    mensagens = [
        EpubCheckMessage("RSC-016", "FATAL", "etiqueta", "OEBPS/Text/cap1.xhtml", 6, 36),
        EpubCheckMessage("RSC-005", "ERROR", "sem local", "OEBPS/Text/cap1.xhtml", -1, -1),
        EpubCheckMessage("OPF-085", "WARNING", "aviso", "OEBPS/content.opf", 3, 7),
        EpubCheckMessage("INF-001", "INFO", "nota", "", -1, -1),
    ]
    problemas = camada_do_epubcheck.problemas_das_mensagens(mensagens)
    assert [(p.codigo, str(p.local)) for p in problemas] == [
        ("epubcheck-erro", "Text/cap1.xhtml:6:36"), ("epubcheck-erro", "Text/cap1.xhtml:0:0"),
        ("epubcheck-aviso", "content.opf:3:7"), ("epubcheck-nota", "(o pacote):0:0")]


def _modulos_da_validacao() -> list[str]:
    pasta = RAIZ / "src" / "caissa" / "editor" / "validacao"
    return sorted(p.stem for p in pasta.glob("*.py") if p.stem != "__init__")


@pytest.mark.parametrize("modulo", _modulos_da_validacao())
def test_a_validacao_nao_conhece_toolkit(modulo: str) -> None:
    """R1.11: nada na thread da janela, e nada de Qt no pacote (o da ui cobre só `editor/*.py`)."""
    caminho = RAIZ / "src" / "caissa" / "editor" / "validacao" / f"{modulo}.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    importados = {a.name.split(".")[0] for n in ast.walk(arvore) if isinstance(n, ast.Import)
                  for a in n.names} | {n.module.split(".")[0] for n in ast.walk(arvore)
                                       if isinstance(n, ast.ImportFrom) and n.module}
    assert not importados & {"PyQt6", "PySide6", "PyQt5", "PySide2"}
    saida = subprocess.run(  # noqa: S603 - o Python dos testes, com um import nosso
        [sys.executable, "-c", f"import sys; import caissa.editor.validacao.{modulo}; "
         "print(sorted(m for m in sys.modules if m.startswith(('PyQt', 'PySide'))))"],
        capture_output=True, text=True, check=True, cwd=RAIZ,
        env={"PYTHONPATH": str(RAIZ / "src"), "SYSTEMROOT": "C:\\Windows"})
    assert saida.stdout.strip() == "[]"


def test_a_previa_resolve_as_variaveis_da_raiz() -> None:
    css = (":root { --tinta: #123456; --realce: var(--tinta); }\n"
           "@media (prefers-color-scheme: dark) { :root { --tinta: #eeeeee; } }\n"
           "p { color: var(--tinta); border-color: var(--realce);"
           " background: var(--falta, #fff); }")
    resolvido = resolver_variaveis(css)
    assert "color: #123456" in resolvido
    assert "border-color: #123456" in resolvido
    assert "background: #fff" in resolvido


def test_a_paginacao_do_mupdf_tem_teto() -> None:
    """O laço do H1: a quebra antes do primeiro elemento pagina para sempre sem o teto."""
    paginado = paginar("<p>um</p><p>dois</p>", "p { page-break-before: always; }", maximo=8)
    assert paginado.laco
    assert paginado.paginas == 8
    assert not paginar("<p>um</p>", "").laco
