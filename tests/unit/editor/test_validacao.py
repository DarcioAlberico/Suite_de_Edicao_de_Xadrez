"""A validação em camadas (Editor HTML/CSS, H10): cada regra acusa o seu defeito, no lugar certo.

O portão inteiro (o IR real limpo, o EPUBCheck, o tempo) é o `benchmarks/editor_validacao.py`;
aqui, o que roda sem Java e sem a máquina livre: os defeitos um a um, o limpo do contrato e o
adversarial, as fixtures que saem dos geradores byte a byte, os consertos, as colunas, o local do
EPUBCheck, a fronteira sem Qt, e o que o ciclo 1 do crítico pediu do contraste e das imagens.
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
from caissa.editor.validacao import REGRAS, Contexto, validar_arquivo, validar_projeto
from caissa.editor.validacao import epubcheck as camada_do_epubcheck
from caissa.editor.validacao.acessibilidade import _candidatos as candidatos_do_srcset
from caissa.editor.validacao.acessibilidade import animada
from caissa.editor.validacao.pagina import cores_em_hex, substituir
from caissa.editor.validacao.xml import LIMITE_DE_BYTES, ler
from caissa.export.epubcheck import EpubCheckMessage

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "benchmarks"))
import editor_contrato  # noqa: E402

DEFEITOS = RAIZ / "tests" / "fixtures" / "editor" / "defeitos"
LIMPOS = RAIZ / "tests" / "fixtures" / "editor" / "limpos"
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
        mapa=mapa_de_json(json.loads(ARQUIVOS[dados["mapa"]])) if "mapa" in dados else None,
        **{chave: dados[chave] for chave in ("nav", "teto_de_paginas") if chave in dados})


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


def test_o_limpo_adversarial_nao_acusa_nada_que_bloqueie_ou_avise() -> None:
    """O que está perto de um defeito sem ser um (o ciclo 1 do crítico): nada bloqueia ou avisa."""
    arquivos = _arquivos(LIMPOS)
    resultado = validar_projeto(Contexto(arquivos=arquivos, nav="Text/nav.xhtml"))
    assert set(resultado) == {n for n in arquivos if n.endswith((".xhtml", ".css"))}
    assert [str(p) for problemas in resultado.values() for p in problemas
            if p.severidade != "informa"] == []


@pytest.mark.parametrize("pasta", [DEFEITOS, LIMPOS], ids=["defeitos", "limpos"])
def test_as_fixtures_sao_do_gerador(pasta: Path, tmp_path: Path) -> None:
    """Regeradas numa pasta à parte, as fixtures saem iguais às do repositório, byte a byte."""
    gerador = next(pasta.glob("gerar_*.py"))
    subprocess.run([sys.executable, str(gerador), str(tmp_path)],  # noqa: S603 - o gerador nosso
                   check=True, capture_output=True, cwd=RAIZ)
    geradas = {p.relative_to(tmp_path).as_posix(): p.read_bytes()
               for p in tmp_path.rglob("*") if p.is_file()}
    guardadas = {p.relative_to(pasta).as_posix(): p.read_bytes()
                 for p in pasta.rglob("*") if p.is_file() and p != gerador
                 and "__pycache__" not in p.parts}
    assert sorted(geradas) == sorted(guardadas)
    assert [n for n in geradas if geradas[n] != guardadas[n]] == []


def test_a_imagem_animada_pela_estrutura() -> None:
    """O GIF de um quadro com o laço do NETSCAPE é estático; o APNG, o WebP e o GIF de dois
    quadros são animados."""
    assert animada(ARQUIVOS["Images/animada.gif"])
    assert animada(ARQUIVOS["Images/animada.png"])
    assert animada(ARQUIVOS["Images/animada.webp"])
    assert not animada((LIMPOS / "Images" / "estatica.gif").read_bytes())
    assert not animada(ARQUIVOS["Images/imagem.png"])
    assert not animada(b"GIF89a")


def test_o_srcset_da_cada_endereco() -> None:
    assert candidatos_do_srcset("a.png 1x, b.gif 2x,c.png") == ["a.png", "b.gif", "c.png"]
    assert candidatos_do_srcset(" ") == []


def test_as_cores_que_o_mupdf_erra_viram_hex() -> None:
    assert cores_em_hex("rgba(0, 0, 0, 0.5)") == "#00000080"
    assert cores_em_hex("hsl(0, 0%, 50%)") == "#808080"
    assert cores_em_hex("rgb(255 0 0 / 50%)") == "#ff000080"
    assert cores_em_hex("1px solid rgba(255,255,255,1)") == "1px solid #ffffff"
    assert cores_em_hex("rebeccapurple", nomes=True) == "#663399"
    assert cores_em_hex("transparent", nomes=True) == "transparent"
    assert cores_em_hex("lab(50% 40 59)") == "lab(50% 40 59)"


def test_o_var_sem_valor_invalida_a_declaracao() -> None:
    assert substituir("var(--a)", {"--a": "#123"}) == "#123"
    assert substituir("var(--falta, var(--a))", {"--a": "#123"}) == "#123"
    assert substituir("var(--falta)", {}) is None


def test_o_contraste_mede_o_capitulo_inteiro() -> None:
    """A página medida é alta: o texto depois de 200 páginas A5 também é medido (o teto velho)."""
    corpo = "\n".join(f"<p>Linha {n} do capítulo comprido.</p>" for n in range(1, 4001))
    texto = ('<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR"><head><title>t</title>'
             f'</head><body>\n{corpo}\n<p style="color: #999999">A última, cinza.</p>\n'
             "</body></html>")
    problemas = validar_arquivo("Text/longo.xhtml", texto)
    assert [(p.codigo, p.local.linha) for p in problemas] == [("css-contraste", 4002)]


def test_o_import_alem_do_limite_de_defesa_e_dito(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cadeia de @import que passa do limite de defesa não some em silêncio (o ciclo 2)."""
    from caissa.editor.validacao import pagina

    nome = "Text/css-contraste-import.xhtml"
    texto = ARQUIVOS[nome].decode("utf-8")
    assert [p.codigo for p in validar_arquivo(nome, texto, Contexto(arquivos=ARQUIVOS))] == [
        "css-contraste"], "a cor da sexta folha é medida"
    monkeypatch.setattr(pagina, "LIMITE_DE_IMPORTS", 2)
    problemas = validar_arquivo(nome, texto, Contexto(arquivos=ARQUIVOS))
    link = next(e for e in ler(nome, texto)[0].elementos() if e.nome == "link")
    assert [(p.codigo, p.local.linha, p.local.coluna) for p in problemas] == [
        ("css-contraste-incompleto", link.linha, link.coluna)]
    assert "passa de 2 folhas" in problemas[0].detalhe
