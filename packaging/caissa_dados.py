"""O acervo do usuario -- rotulos, amostras, galeria, estudos, indices e pesos -- de uma
instalacao para outra, sem apagar nada do destino.

Por que este modulo existe
--------------------------
`caissa_modelos.py` traz os **pesos** que nao viajam dentro do binario. Ele nao traz o que o
tronco (`ChessVisionOFF_Puro`) acumulou em meses de uso: 5.400 diagramas rotulados em
`data/labels.csv` + `data/samples/`, os `splits`, a quarentena, o conjunto de campo, a galeria
por livro, os estudos em PGN e o indice de partidas. Um `Caissa.exe` recem-instalado abre
com o dataset vazio -- e o usuario que ja tem esse acervo no checkout quer que o programa
comece de onde ele parou, nao do zero.

O contrato
----------
Origem e destino sao duas **raizes** com o mesmo desenho (`data/`, `models/`), que e o
desenho do tronco e o da pasta do `.exe` (`chess_diagram_ocr.config._project_root`,
`caissa_modelos.raiz_de_instalacao`). Cada item do `ACERVO` diz **como** se funde:

* ``csv-por-filename`` -- `labels.csv`, `splits.csv`, `quarantine.csv`: entra a linha cuja
  `filename` o destino nao tem; colunas sao a uniao das duas cabeceiras (o `LabelStore` do
  tronco le por nome). Em `labels.csv` a linha so entra com a amostra ao lado
  (`data/samples/<filename>`), copiada junto; sem o PNG a linha e recusada e contada.
* ``jsonl-por-chave`` -- `field_set.jsonl` (chave `pdf`+`page`), `gallery_human.jsonl`
  (`book`+`at`): entra a linha cuja chave o destino nao tem. **O destino ganha o empate**: a
  pagina anotada de novo aqui nao e desfeita pela copia antiga de la.
* ``pasta-sem-sobrescrever`` -- `gallery/`, `estudos/`, `samples/` orfaos: arquivo a arquivo,
  so o que falta.
* ``arquivo-se-ausente`` -- indices SQLite e os tres pesos do manifesto: so quando o destino
  nao os tem; existente e diferente e **relatado**, nunca trocado (pode ser um modelo que o
  usuario ajustou aqui).
* ``substituir`` -- so `models/tessdata/livros/` e `livros.json`: sao artefatos do treinador
  da suite (`caissa-treinar`), nao trabalho feito na janela; a versao mais nova vence.

Tudo e **rascunho por padrao**: sem `--gravar` o modulo so conta e diz o que faria. Copias
sao atomicas por renomeacao (`.parcial` -> nome final), como em `caissa_modelos`.

O que fica de fora, de proposito: `review_cache/` (10 GB de cache, refaz-se), `orphans/`,
`*.bak-*`, `janela.json`/`settings.json` (estado da janela **desta** maquina) e
`app_tkinter_state.json`.

Uso::

    python packaging/caissa_dados.py --de C:/Python-Chess2/ChessVisionOFF_Puro --para dist/Caissa
    python packaging/caissa_dados.py --de ... --para ... --gravar
    Caissa.exe --importar-acervo C:/Python-Chess2/ChessVisionOFF_Puro        # grava na pasta do .exe

E o caminho de volta e o mesmo comando com os papeis trocados: o que se anotou na janela do
`.exe` (`data/field_set.jsonl`, amostras novas) volta ao tronco sem desfazer nada de la.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["ACERVO", "Item", "Relatorio", "importar", "main"]

TAMANHO_DO_BLOCO = 1 << 20


@dataclass(frozen=True)
class Item:
    caminho: str
    """Relativo a raiz, com barras normais. Pode ter `*` (glob simples no nome)."""
    modo: str
    chave: tuple[str, ...] = ()
    """Para `jsonl-por-chave`: os campos que identificam a linha."""
    amostras: str = ""
    """Para `csv-por-filename`: a pasta cujo arquivo `filename` tem de existir e vem junto."""
    o_que_e: str = ""


ACERVO: tuple[Item, ...] = (
    Item("data/labels.csv", "csv-por-filename", amostras="data/samples",
         o_que_e="diagramas rotulados (o dataset de treino), com a amostra ao lado"),
    Item("data/splits.csv", "csv-por-filename", o_que_e="train/val/test por amostra"),
    Item("data/quarantine.csv", "csv-por-filename", o_que_e="rotulos postos de lado, com o motivo"),
    Item("data/field_set.jsonl", "jsonl-por-chave", chave=("pdf", "page"),
         o_que_e="conjunto de campo (paginas anotadas a mao)"),
    Item("data/gallery_human.jsonl", "jsonl-por-chave", chave=("book", "at"),
         o_que_e="cabecalhos de partida corrigidos na galeria"),
    Item("data/gallery", "pasta-sem-sobrescrever", o_que_e="galeria por livro"),
    Item("data/estudos", "pasta-sem-sobrescrever", o_que_e="estudos em PGN"),
    Item("data/samples", "pasta-sem-sobrescrever",
         o_que_e="amostras sem linha em labels.csv (orfas do dataset)"),
    Item("data/games_index.sqlite", "arquivo-se-ausente", o_que_e="indice de partidas"),
    Item("data/games_positions*.sqlite", "arquivo-se-ausente", o_que_e="posicoes indexadas por base"),
    Item("models/piece_classifier.pt", "arquivo-se-ausente", o_que_e="classificador de pecas"),
    Item("models/char_classifier.pt", "arquivo-se-ausente", o_que_e="classificador de caracteres (glifo)"),
    Item("models/char_meta.json", "arquivo-se-ausente", o_que_e="metadados do classificador de caracteres"),
    Item("models/tessdata/livros", "substituir", o_que_e="modelos Tesseract por livro (caissa-treinar)"),
    Item("models/tessdata/livros.json", "substituir", o_que_e="registro dos modelos por livro"),
)


@dataclass
class Relatorio:
    gravar: bool
    linhas: list[str] = field(default_factory=list)
    entradas: int = 0
    arquivos: int = 0
    bytes: int = 0
    recusadas: int = 0
    diferentes: list[str] = field(default_factory=list)
    ausentes_na_origem: list[str] = field(default_factory=list)
    substituir: frozenset[str] = frozenset()
    """Caminhos relativos que `arquivo-se-ausente` pode trocar mesmo existindo (pedido explicito)."""
    planejados: set[Path] = field(default_factory=set)
    """Destinos ja copiados (ou que seriam, no rascunho): o que labels.csv trouxe, samples/ nao reconta."""

    def diz(self, texto: str) -> None:
        self.linhas.append(texto)

    def as_dict(self) -> dict[str, Any]:
        return {
            "gravado": self.gravar, "entradas": self.entradas, "arquivos": self.arquivos,
            "bytes": self.bytes, "recusadas": self.recusadas, "diferentes": self.diferentes,
            "ausentes_na_origem": self.ausentes_na_origem, "linhas": self.linhas,
        }


# ----------------------------------------------------------------------------- primitivas

def _copiar_atomico(origem: Path, destino: Path, relatorio: Relatorio) -> None:
    relatorio.arquivos += 1
    relatorio.bytes += origem.stat().st_size
    relatorio.planejados.add(destino)
    if not relatorio.gravar:
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    shutil.copy2(origem, parcial)
    parcial.replace(destino)


def _escrever_atomico(destino: Path, texto: str, relatorio: Relatorio) -> None:
    if not relatorio.gravar:
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    parcial.write_text(texto, encoding="utf-8", newline="")
    parcial.replace(destino)


def _iguais(a: Path, b: Path) -> bool:
    if a.stat().st_size != b.stat().st_size:
        return False
    with a.open("rb") as fa, b.open("rb") as fb:
        while True:
            ba, bb = fa.read(TAMANHO_DO_BLOCO), fb.read(TAMANHO_DO_BLOCO)
            if ba != bb:
                return False
            if not ba:
                return True


def _ler_csv(caminho: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not caminho.is_file():
        return [], []
    with caminho.open("r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        colunas = list(leitor.fieldnames or [])
        return colunas, [dict(linha) for linha in leitor]


def _escrever_csv(colunas: list[str], linhas: list[dict[str, str]]) -> str:
    import io

    saida = io.StringIO()
    escritor = csv.DictWriter(saida, fieldnames=colunas, extrasaction="ignore", lineterminator="\n")
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow({c: linha.get(c, "") or "" for c in colunas})
    return saida.getvalue()


def _ler_jsonl(caminho: Path) -> list[dict[str, Any]]:
    if not caminho.is_file():
        return []
    linhas: list[dict[str, Any]] = []
    for bruto in caminho.read_text(encoding="utf-8").splitlines():
        texto = bruto.strip()
        if texto and not texto.startswith("//"):
            linhas.append(json.loads(texto))
    return linhas


# ------------------------------------------------------------------------------- os modos

def _csv_por_filename(item: Item, origem: Path, destino: Path, relatorio: Relatorio) -> None:
    fonte = origem / item.caminho
    alvo = destino / item.caminho
    if not fonte.is_file():
        relatorio.ausentes_na_origem.append(item.caminho)
        return
    col_o, linhas_o = _ler_csv(fonte)
    col_d, linhas_d = _ler_csv(alvo)
    if "filename" not in col_o:
        relatorio.diz(f"  ! {item.caminho}: a origem nao tem a coluna filename; pulado")
        return
    conhecidos = {linha.get("filename", "") for linha in linhas_d}
    colunas = list(col_d) + [c for c in col_o if c not in col_d]
    novas: list[dict[str, str]] = []
    sem_amostra = 0
    for linha in linhas_o:
        nome = linha.get("filename", "")
        if not nome or nome in conhecidos:
            continue
        if item.amostras:
            png_o = origem / item.amostras / nome
            png_d = destino / item.amostras / nome
            if not png_o.is_file():
                sem_amostra += 1
                continue
            if not png_d.is_file() and png_d not in relatorio.planejados:
                _copiar_atomico(png_o, png_d, relatorio)
        novas.append(linha)
        conhecidos.add(nome)
    relatorio.entradas += len(novas)
    relatorio.recusadas += sem_amostra
    if novas or (colunas != col_d and linhas_d):
        _escrever_atomico(alvo, _escrever_csv(colunas, linhas_d + novas), relatorio)
    extra = f", {sem_amostra} sem a amostra (recusadas)" if sem_amostra else ""
    relatorio.diz(f"  + {item.caminho}: {len(novas)} linhas novas (destino tinha {len(linhas_d)}){extra}")


def _jsonl_por_chave(item: Item, origem: Path, destino: Path, relatorio: Relatorio) -> None:
    fonte = origem / item.caminho
    alvo = destino / item.caminho
    if not fonte.is_file():
        relatorio.ausentes_na_origem.append(item.caminho)
        return
    linhas_o, linhas_d = _ler_jsonl(fonte), _ler_jsonl(alvo)

    def chave(linha: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(linha.get(c, "")) for c in item.chave)

    conhecidas = {chave(linha) for linha in linhas_d}
    novas = [linha for linha in linhas_o if chave(linha) not in conhecidas]
    relatorio.entradas += len(novas)
    if novas:
        corpo = "".join(json.dumps(linha, ensure_ascii=False) + "\n" for linha in linhas_d + novas)
        _escrever_atomico(alvo, corpo, relatorio)
    relatorio.diz(f"  + {item.caminho}: {len(novas)} linhas novas (destino tinha {len(linhas_d)})")


def _pasta_sem_sobrescrever(item: Item, origem: Path, destino: Path, relatorio: Relatorio) -> None:
    fonte = origem / item.caminho
    if not fonte.is_dir():
        relatorio.ausentes_na_origem.append(item.caminho)
        return
    novos = 0
    for arquivo in sorted(p for p in fonte.rglob("*") if p.is_file()):
        if arquivo.name.endswith(".parcial") or ".bak-" in arquivo.name:
            continue
        alvo = destino / item.caminho / arquivo.relative_to(fonte)
        if alvo.exists() or alvo in relatorio.planejados:
            continue
        _copiar_atomico(arquivo, alvo, relatorio)
        novos += 1
    relatorio.diz(f"  + {item.caminho}/: {novos} arquivos novos")


def _arquivo_se_ausente(item: Item, origem: Path, destino: Path, relatorio: Relatorio) -> None:
    padrao = Path(item.caminho)
    fontes = sorted(origem.joinpath(padrao.parent).glob(padrao.name)) if "*" in padrao.name \
        else [origem / item.caminho]
    fontes = [f for f in fontes if f.is_file()]
    if not fontes:
        relatorio.ausentes_na_origem.append(item.caminho)
        return
    for fonte in fontes:
        alvo = destino / fonte.relative_to(origem)
        relativo = alvo.relative_to(destino).as_posix()
        if alvo.is_file():
            if _iguais(fonte, alvo):
                relatorio.diz(f"  = {relativo}: igual, nada a fazer")
                continue
            if relativo not in relatorio.substituir:
                relatorio.diferentes.append(relativo)
                relatorio.diz(f"  = {relativo}: existe e DIFERE; mantido o do destino "
                              f"(--substituir {relativo} para trocar)")
                continue
            relatorio.diz(f"  ~ {relativo}: substituido a pedido ({fonte.stat().st_size >> 20} MB)")
        else:
            relatorio.diz(f"  + {relativo}: copiado ({fonte.stat().st_size >> 20} MB)")
        _copiar_atomico(fonte, alvo, relatorio)


def _substituir(item: Item, origem: Path, destino: Path, relatorio: Relatorio) -> None:
    fonte = origem / item.caminho
    if not fonte.exists():
        relatorio.ausentes_na_origem.append(item.caminho)
        return
    if not (destino / "models" / "tessdata").is_dir():
        # O tronco nao tem `models/tessdata`: ele nao roda o OCR da suite, e despejar 3.000
        # arquivos de modelo la seria lixo. So entra onde ja existe a pasta que os usa.
        relatorio.diz(f"  - {item.caminho}: o destino nao tem models/tessdata; pulado")
        return
    arquivos = [fonte] if fonte.is_file() else sorted(p for p in fonte.rglob("*") if p.is_file())
    trocados = 0
    for arquivo in arquivos:
        if arquivo.name.endswith(".parcial"):
            continue
        alvo = destino / arquivo.relative_to(origem)
        if alvo.is_file() and _iguais(arquivo, alvo):
            continue
        _copiar_atomico(arquivo, alvo, relatorio)
        trocados += 1
    relatorio.diz(f"  + {item.caminho}: {trocados} arquivos copiados ou substituidos")


_MODOS = {
    "csv-por-filename": _csv_por_filename,
    "jsonl-por-chave": _jsonl_por_chave,
    "pasta-sem-sobrescrever": _pasta_sem_sobrescrever,
    "arquivo-se-ausente": _arquivo_se_ausente,
    "substituir": _substituir,
}


def importar(
    origem: Path,
    destino: Path,
    *,
    gravar: bool = False,
    itens: tuple[Item, ...] = ACERVO,
    tessdata_de: Path | None = None,
    substituir: frozenset[str] = frozenset(),
) -> Relatorio:
    """Funde o acervo de `origem` em `destino`. Ver o docstring do modulo para as regras.

    `tessdata_de` e a raiz de onde vem `models/tessdata/livros` quando ela nao e a mesma da
    origem -- no checkout, os modelos por livro moram na suite, e o dataset no tronco.
    """
    origem, destino = Path(origem).resolve(), Path(destino).resolve()
    if origem == destino:
        raise ValueError("origem e destino sao a mesma pasta")
    relatorio = Relatorio(gravar=gravar, substituir=frozenset(substituir))
    relatorio.diz(f"{'GRAVANDO' if gravar else 'RASCUNHO'}: {origem} -> {destino}")
    for item in itens:
        raiz = tessdata_de if (tessdata_de and item.caminho.startswith("models/tessdata/")) else origem
        _MODOS[item.modo](item, Path(raiz).resolve(), destino, relatorio)
    return relatorio


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__,
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
    analisador.add_argument("--de", type=Path, required=True,
                            help="raiz de origem (tronco, ou outra pasta do Caissa)")
    analisador.add_argument("--para", type=Path, default=None,
                            help="raiz de destino (padrao: a pasta do .exe; no checkout, a suite)")
    analisador.add_argument("--tessdata-de", type=Path, default=None,
                            help="raiz de onde vem models/tessdata/livros (padrao: a suite)")
    analisador.add_argument("--substituir", action="append", default=[], metavar="CAMINHO",
                            help="arquivo (relativo) que pode ser trocado mesmo existindo diferente")
    analisador.add_argument("--gravar", action="store_true", help="escreve; sem isto so mostra o que faria")
    analisador.add_argument("--json", action="store_true", help="emite o relatorio em JSON")
    args = analisador.parse_args(argv)

    from caissa_modelos import raiz_de_instalacao

    destino = args.para or raiz_de_instalacao()
    tessdata_de = args.tessdata_de
    if tessdata_de is None and not getattr(sys, "frozen", False):
        tessdata_de = Path(__file__).resolve().parents[1]
    try:
        relatorio = importar(args.de, destino, gravar=args.gravar, tessdata_de=tessdata_de,
                             substituir=frozenset(c.replace("\\", "/") for c in args.substituir))
    except ValueError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(relatorio.as_dict(), ensure_ascii=False, indent=2))
    else:
        print("\n".join(relatorio.linhas))
        resumo = (f"total: {relatorio.entradas} entradas, {relatorio.arquivos} arquivos, "
                  f"{relatorio.bytes / (1 << 20):.0f} MB, {relatorio.recusadas} recusadas")
        if relatorio.diferentes:
            resumo += f", {len(relatorio.diferentes)} diferentes mantidos"
        if relatorio.ausentes_na_origem:
            resumo += f"; ausentes na origem: {', '.join(relatorio.ausentes_na_origem)}"
        print(resumo)
        if not args.gravar:
            print("rascunho -- nada gravado (use --gravar)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
