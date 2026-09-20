"""`packaging/caissa_dados.py`: o acervo funde sem apagar, e o rascunho nao toca no disco.

Cada modo do `ACERVO` tem um teste que afirma a regra do docstring do modulo, com pastas
temporarias e arquivos de mentira -- o que importa e a semantica da fusao, nao o dataset.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "packaging"
if str(PACOTE) not in sys.path:
    sys.path.insert(0, str(PACOTE))

import caissa_dados  # noqa: E402


def _csv(caminho: Path, cabecalho: str, *linhas: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join([cabecalho, *linhas]) + "\n", encoding="utf-8")


def _png(caminho: Path, conteudo: bytes = b"png") -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)


@pytest.fixture
def raizes(tmp_path: Path) -> tuple[Path, Path]:
    origem, destino = tmp_path / "origem", tmp_path / "destino"
    origem.mkdir()
    destino.mkdir()
    return origem, destino


def test_labels_entram_por_filename_e_so_com_a_amostra(raizes: tuple[Path, Path]) -> None:
    origem, destino = raizes
    _csv(origem / "data/labels.csv", "filename,fen,extra", "a.png,8/8,x", "b.png,8/8,y", "c.png,8/8,z")
    _png(origem / "data/samples/a.png")
    _png(origem / "data/samples/b.png")
    # c.png nao tem amostra: recusada. b.png ja existe no destino com outra FEN: mantida.
    _csv(destino / "data/labels.csv", "filename,fen", "b.png,7/8")
    _png(destino / "data/samples/b.png", b"meu")

    relatorio = caissa_dados.importar(origem, destino, gravar=True, itens=caissa_dados.ACERVO[:1])

    colunas, linhas = caissa_dados._ler_csv(destino / "data/labels.csv")
    assert colunas == ["filename", "fen", "extra"], "uniao das cabeceiras, as do destino primeiro"
    assert [(linha["filename"], linha["fen"]) for linha in linhas] == [("b.png", "7/8"), ("a.png", "8/8")]
    assert (destino / "data/samples/a.png").read_bytes() == b"png"
    assert (destino / "data/samples/b.png").read_bytes() == b"meu", "a amostra do destino nao e trocada"
    assert relatorio.entradas == 1
    assert relatorio.recusadas == 1


def test_rascunho_nao_escreve_nada(raizes: tuple[Path, Path]) -> None:
    origem, destino = raizes
    _csv(origem / "data/labels.csv", "filename,fen", "a.png,8/8")
    _png(origem / "data/samples/a.png")
    (origem / "data/gallery").mkdir(parents=True)
    (origem / "data/gallery/x.json").write_text("{}", encoding="utf-8")

    relatorio = caissa_dados.importar(origem, destino, gravar=False)

    assert sorted(p.name for p in destino.rglob("*")) == [], "rascunho: o destino continua vazio"
    assert relatorio.entradas == 1
    assert relatorio.arquivos == 2, "mas conta o que faria"


def test_amostra_trazida_pelo_labels_nao_e_recontada_pelo_samples(raizes: tuple[Path, Path]) -> None:
    origem, destino = raizes
    _csv(origem / "data/labels.csv", "filename,fen", "a.png,8/8")
    _png(origem / "data/samples/a.png")
    _png(origem / "data/samples/orfa.png")

    relatorio = caissa_dados.importar(origem, destino, gravar=False)

    assert relatorio.arquivos == 2, "a.png uma vez (pelo labels) e a orfa uma vez (pelo samples)"


def test_jsonl_por_chave_e_o_destino_ganha_o_empate(raizes: tuple[Path, Path]) -> None:
    origem, destino = raizes
    (origem / "data").mkdir()
    (destino / "data").mkdir()
    (origem / "data/field_set.jsonl").write_text(
        json.dumps({"pdf": "a.pdf", "page": 1, "diagrams": ["velho"]}) + "\n"
        + json.dumps({"pdf": "a.pdf", "page": 2, "diagrams": []}) + "\n",
        encoding="utf-8",
    )
    (destino / "data/field_set.jsonl").write_text(
        json.dumps({"pdf": "a.pdf", "page": 1, "diagrams": ["novo"]}) + "\n", encoding="utf-8"
    )

    caissa_dados.importar(origem, destino, gravar=True)

    linhas = caissa_dados._ler_jsonl(destino / "data/field_set.jsonl")
    assert [(linha["page"], linha["diagrams"]) for linha in linhas] == [(1, ["novo"]), (2, [])]


def test_arquivo_se_ausente_relata_o_diferente_e_troca_so_a_pedido(raizes: tuple[Path, Path]) -> None:
    origem, destino = raizes
    _png(origem / "models/piece_classifier.pt", b"treinado la")
    _png(destino / "models/piece_classifier.pt", b"ajustado aqui")
    _png(origem / "data/games_index.sqlite", b"indice")

    relatorio = caissa_dados.importar(origem, destino, gravar=True)
    assert (destino / "models/piece_classifier.pt").read_bytes() == b"ajustado aqui"
    assert relatorio.diferentes == ["models/piece_classifier.pt"]
    assert (destino / "data/games_index.sqlite").read_bytes() == b"indice"

    caissa_dados.importar(origem, destino, gravar=True, substituir=frozenset({"models/piece_classifier.pt"}))
    assert (destino / "models/piece_classifier.pt").read_bytes() == b"treinado la"


def test_tessdata_por_livro_substitui_mas_so_onde_ha_tessdata(raizes: tuple[Path, Path]) -> None:
    origem, destino = raizes
    _png(origem / "models/tessdata/livros/x/caissa_eng.traineddata", b"v2")
    _png(destino / "models/tessdata/livros/x/caissa_eng.traineddata", b"v1")

    caissa_dados.importar(origem, destino, gravar=True)
    assert (destino / "models/tessdata/livros/x/caissa_eng.traineddata").read_bytes() == b"v2"

    tronco = destino.parent / "tronco"
    tronco.mkdir()
    relatorio = caissa_dados.importar(origem, tronco, gravar=True)
    assert not (tronco / "models/tessdata").exists()
    assert any("pulado" in linha for linha in relatorio.linhas)


def test_mesma_pasta_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mesma pasta"):
        caissa_dados.importar(tmp_path, tmp_path)


def test_origem_inexistente_e_erro(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nao existe"):
        caissa_dados.importar(tmp_path / "nada", tmp_path)
