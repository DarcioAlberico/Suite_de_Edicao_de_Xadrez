"""O projeto do editor em disco (passo H6): nada se perde, um livro por janela.

Cada regra com um caso feito à mão. A prova sob queda de verdade — um processo filho morto por
`TerminateProcess` no meio da gravação, 50 vezes — é o `benchmarks/editor_recuperacao.py`, pelo
executor de portões; aqui ficam os casos que um teste de unidade alcança.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from caissa.editor import gravacao, migracoes
from caissa.editor.livros import IndiceDeLivros, slug
from caissa.editor.projeto import (
    CaminhoInvalido,
    EstadoDaPagina,
    ProjetoDoEditor,
    validar_arquivo,
)
from caissa.editor.trava import NOME, LivroJaAberto, Trava, processo_vivo
from caissa.editor.versoes import Versoes

CAP = "OEBPS/Text/cap-01.xhtml"


def _pdf(destino: Path, paginas: int = 3, texto: str = "Um livro") -> Path:
    import pymupdf

    documento = pymupdf.open()
    for numero in range(paginas):
        pagina = documento.new_page()
        pagina.insert_text((72, 72), f"{texto}, página {numero + 1}")
    documento.save(str(destino))
    documento.close()
    return destino


def _pid_morto() -> int:
    filho = subprocess.Popen([sys.executable, "-c", "pass"])  # noqa: S603 - o próprio Python
    filho.wait()
    return filho.pid


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    return _pdf(tmp_path / "Um Livro de Finais — 2ª ed.pdf")


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    return tmp_path / "editor"


def test_criar_monta_a_pasta_o_indice_e_o_projeto(pdf: Path, raiz: Path) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        assert projeto.pasta.parent == raiz
        assert projeto.pasta.name == slug(pdf.stem)
        for sub in ("OEBPS/Text", "OEBPS/Styles", "OEBPS/Images"):
            assert (projeto.pasta / sub).is_dir()
        dados = json.loads((projeto.pasta / "projeto.json").read_text(encoding="utf-8"))
        assert dados["formato"] == migracoes.FORMATO_ATUAL
        assert dados["pdf_nome"] == pdf.name
        assert sorted(dados["paginas"]) == ["1", "2", "3"]
        assert projeto.estado(2) is EstadoDaPagina.NAO_GERADA
        indice = json.loads((raiz / "livros.json").read_text(encoding="utf-8"))
        assert indice[dados["pdf_sha256"]]["pasta"] == projeto.pasta.name


def test_o_livro_renomeado_acha_o_mesmo_projeto(pdf: Path, raiz: Path) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        pasta = projeto.pasta
    renomeado = pdf.rename(pdf.with_name("outro nome.pdf"))
    with ProjetoDoEditor.abrir(renomeado, raiz=raiz) as projeto:
        assert projeto.pasta == pasta


def test_dois_livros_de_mesmo_nome_nao_dividem_a_pasta(tmp_path: Path, raiz: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    primeiro = _pdf(tmp_path / "a" / "livro.pdf", texto="primeiro")
    segundo = _pdf(tmp_path / "b" / "livro.pdf", texto="segundo")
    with ProjetoDoEditor.criar(primeiro, raiz=raiz) as um, \
            ProjetoDoEditor.criar(segundo, raiz=raiz) as outro:
        assert um.pasta != outro.pasta
        assert outro.pasta.name == "livro-2"


def test_a_segunda_abertura_do_mesmo_livro_e_recusada(pdf: Path, raiz: Path) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz), \
            pytest.raises(LivroJaAberto, match="já está aberto"):
        ProjetoDoEditor.abrir(pdf, raiz=raiz)
    with ProjetoDoEditor.abrir(pdf, raiz=raiz) as projeto:     # fechada a primeira, abre
        assert projeto.trava.caminho.exists()


def test_a_trava_de_processo_morto_e_retomada(tmp_path: Path) -> None:
    import platform

    agora = time.time()
    (tmp_path / NOME).write_text(json.dumps({"pid": _pid_morto(), "maquina": platform.node(),
                                             "desde": agora, "ate": agora + 3600}),
                                 encoding="utf-8")
    with Trava.adquirir(tmp_path) as trava:
        assert trava.dono.pid == os.getpid()


def test_a_trava_vencida_e_retomada_mesmo_com_o_pid_vivo(tmp_path: Path) -> None:
    """O Windows reaproveita PID: o vivo que não renovou perde a trava pela validade."""
    import platform

    agora = time.time()
    (tmp_path / NOME).write_text(json.dumps({"pid": os.getpid(), "maquina": platform.node(),
                                             "desde": agora - 7200, "ate": agora - 10}),
                                 encoding="utf-8")
    with Trava.adquirir(tmp_path) as trava:
        assert trava.dono.ate > agora


def test_soltar_nao_apaga_a_trava_que_outro_retomou(tmp_path: Path) -> None:
    trava = Trava.adquirir(tmp_path)
    (tmp_path / NOME).write_text(json.dumps({"pid": 1, "maquina": "outra", "desde": 1.0,
                                             "ate": time.time() + 60}), encoding="utf-8")
    trava.soltar()
    assert (tmp_path / NOME).exists()


def test_processo_vivo_distingue_vivo_e_morto() -> None:
    assert processo_vivo(os.getpid())
    assert not processo_vivo(_pid_morto())
    assert not processo_vivo(0)


def test_gravar_devolve_o_antigo_quando_a_troca_falha(pdf: Path, raiz: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        projeto.gravar(CAP, "<p>antigo</p>")

        def falha(*_: object) -> None:
            raise OSError("disco cheio")

        monkeypatch.setattr(gravacao.os, "replace", falha)
        with pytest.raises(OSError, match="disco cheio"):
            projeto.gravar(CAP, "<p>novo</p>")
        assert (projeto.pasta / CAP).read_text(encoding="utf-8") == "<p>antigo</p>"
        assert not list((projeto.pasta / "OEBPS" / "Text").glob(".*.parcial"))


def test_os_parciais_de_processo_morto_saem_na_abertura(pdf: Path, raiz: Path) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        pasta = projeto.pasta
        projeto.gravar(CAP, "<p>ok</p>")
    morto = gravacao.caminho_parcial(pasta / CAP, pid=_pid_morto())
    vivo = gravacao.caminho_parcial(pasta / CAP)
    morto.write_bytes(b"pela metade")
    vivo.write_bytes(b"gravando agora")
    with ProjetoDoEditor.abrir(pdf, raiz=raiz):
        assert not morto.exists()
        assert vivo.exists()
    vivo.unlink()


def test_cada_gravacao_guarda_uma_versao_e_a_restauracao_e_identica(pdf: Path, raiz: Path) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        textos = [f"<p>versão {n} — ♘f3</p>" for n in range(5)]
        carimbos = [projeto.gravar(CAP, texto) for texto in textos]
        assert [v.carimbo for v in projeto.versao(CAP)] == list(reversed(carimbos))
        projeto.restaurar(carimbos[1], CAP)
        assert (projeto.pasta / CAP).read_bytes() == textos[1].encode("utf-8")
        assert len(projeto.versao(CAP)) == 6


def test_a_poda_respeita_o_teto_e_o_piso(tmp_path: Path) -> None:
    versoes = Versoes(tmp_path, teto_bytes=10_000, piso=3)
    carimbos = [versoes.guardar(CAP, bytes([n]) * 1000) for n in range(30)]
    assert versoes.total_bytes() <= 10_000
    assert {v.carimbo for v in versoes.listar()} >= set(carimbos[-3:])
    grandes = Versoes(tmp_path / "grandes", teto_bytes=10_000, piso=3)
    ultimos = [grandes.guardar(CAP, bytes([n]) * 6000) for n in range(6)]
    assert [v.carimbo for v in grandes.listar()] == list(reversed(ultimos[-3:]))


def test_o_diario_devolve_o_texto_sujo_e_some_ao_gravar(pdf: Path, raiz: Path) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        projeto.gravar(CAP, "<p>gravado</p>")
        projeto.anotar(CAP, "<p>gravado, e depois editado</p>")
    with ProjetoDoEditor.abrir(pdf, raiz=raiz) as projeto:
        recuperado = projeto.recuperar_do_diario()
        assert recuperado[CAP].texto == "<p>gravado, e depois editado</p>"
        projeto.gravar(CAP, recuperado[CAP].texto)
        assert projeto.recuperar_do_diario() == {}


def test_mudou_por_fora_olha_o_conteudo_e_a_data(pdf: Path, raiz: Path) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        projeto.gravar(CAP, "<p>meu</p>")
        caminho = projeto.pasta / CAP
        assert not projeto.mudou_por_fora(CAP)
        antes = caminho.stat()
        caminho.write_text("<p>seu</p>", encoding="utf-8")
        os.utime(caminho, ns=(antes.st_atime_ns, antes.st_mtime_ns))   # devolve a data antiga
        assert projeto.mudou_por_fora(CAP)
        projeto.ler(CAP)
        caminho.write_text("<p>seu</p>", encoding="utf-8")              # o mesmo texto de novo
        assert not projeto.mudou_por_fora(CAP)
        caminho.unlink()
        assert projeto.mudou_por_fora(CAP)


def test_o_editor_so_grava_dentro_do_livro() -> None:
    assert validar_arquivo("OEBPS\\Text\\cap.xhtml") == "OEBPS/Text/cap.xhtml"
    for ruim in ("../fora.xhtml", "OEBPS/../projeto.json", "C:/Windows/win.ini", "/etc/passwd",
                 "projeto.json", "OEBPS"):
        with pytest.raises(CaminhoInvalido):
            validar_arquivo(ruim)


def test_marcar_editada_muda_o_estado_e_grava(pdf: Path, raiz: Path) -> None:
    with ProjetoDoEditor.criar(pdf, raiz=raiz) as projeto:
        projeto.marcar_editada([2])
        assert projeto.estado(2) is EstadoDaPagina.EDITADA
        dados = json.loads((projeto.pasta / "projeto.json").read_text(encoding="utf-8"))
        assert dados["paginas"]["2"]["estado"] == "EDITADA"
        assert "editada_em" in dados["paginas"]["2"]


def test_a_migracao_encadeia_e_recusa_o_formato_mais_novo() -> None:
    assert migracoes.migrar({"formato": 1, "x": 1}) == {"formato": 1, "x": 1}
    passos = {1: lambda d: {**d, "y": 2}, 2: lambda d: {**d, "z": 3}}
    assert migracoes.migrar({"formato": 1}, atual=3, passos=passos) == {"formato": 3, "y": 2,
                                                                        "z": 3}
    with pytest.raises(migracoes.FormatoDesconhecido, match="lê até o 1"):
        migracoes.migrar({"formato": 2})
    with pytest.raises(migracoes.FormatoDesconhecido, match="sem o número do formato"):
        migracoes.migrar({})
    with pytest.raises(migracoes.FormatoDesconhecido, match="falta a migração"):
        migracoes.migrar({"formato": 1}, atual=2, passos={})


def test_o_indice_e_regravado_inteiro(tmp_path: Path) -> None:
    indice = IndiceDeLivros(tmp_path)
    primeira = indice.registrar("a" * 64, "Livro.pdf")
    assert indice.registrar("a" * 64, "Livro renomeado.pdf") == primeira
    assert indice.pasta_de("b" * 64) is None
