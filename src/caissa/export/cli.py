"""``caissa-exportar`` — um PDF vira EPUB ou DOCX, inteiro ou por intervalo de páginas.

O mesmo pipeline do diálogo *Exportar livro…* da janela do produto, para rodar num
terminal ou num job::

    caissa-exportar Livro.pdf --epub
    caissa-exportar Livro.pdf --docx --paginas 10-25
    caissa-exportar Livro.pdf --saida "C:/Livros/Capítulo 3.epub" --paginas "40-, 7"
    caissa-exportar Livro.pdf --epub --sem-ocr

As páginas são **as do PDF, contadas de 1**: ``10-25`` é da décima à vigésima quinta,
``40-`` vai até o fim, ``-3`` começa do início; vírgulas juntam pedaços.  Sem
``--paginas`` sai o livro completo.  Sem ``--saida``, o arquivo nasce ao lado do PDF com
o mesmo nome — e com o intervalo no nome quando é parcial (``Livro (p. 10-25).epub``),
para duas exportações do mesmo livro não se sobrescreverem.  O formato vem de
``--epub``/``--docx`` ou da extensão de ``--saida``.

``--sem-ocr`` é o caminho rápido: páginas sem camada de texto entram como imagem em vez de
esperar o reconhecimento.  A saída termina com o resumo dos dois relatórios — o da
importação (parágrafos, títulos, diagramas, origem de cada página) e o da gravação (o que
o formato não carregou); ``--verboso`` lista as regiões que o OCR deixou para revisão.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from caissa.export.base import ExportError
from caissa.export.book import (
    BOOK_FORMATS,
    PageRangeError,
    export_book,
    format_for_path,
)
from caissa.ingest.pdf import ImportCanceled, PdfOpenError

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="caissa-exportar", description=__doc__.split("\n\n")[0])
    parser.add_argument("pdf", type=Path, help="o livro em PDF")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--epub", action="store_const", const="epub", dest="formato")
    grupo.add_argument("--docx", action="store_const", const="docx", dest="formato")
    parser.add_argument(
        "--paginas",
        default="",
        help="intervalo de páginas contadas de 1, como 10-25 ou '1-3, 7, 40-' (padrão: todas)",
    )
    parser.add_argument(
        "--saida", type=Path, default=None, help="arquivo de saída (padrão: ao lado do PDF)"
    )
    parser.add_argument(
        "--sem-ocr",
        action="store_true",
        help="não reconhecer páginas sem camada de texto; elas entram como imagem",
    )
    parser.add_argument("--verboso", action="store_true", help="listar as regiões para revisão")
    args = parser.parse_args(argv)

    formato: str | None = args.formato
    if formato is None and args.saida is not None:
        try:
            formato = format_for_path(args.saida)
        except ExportError as exc:
            parser.error(str(exc))
    if formato is None:
        extensoes = "/".join(BOOK_FORMATS)
        parser.error(f"diga o formato: --epub, --docx ou --saida com extensão {extensoes}")

    def progresso(fase: str, feito: int, total: int) -> None:
        if fase == "importando" and total:
            sys.stderr.write(f"\r{fase} {feito}/{total}")
        elif fase == "gravando" and feito == total:
            sys.stderr.write("\rgravando…      \n")

    try:
        resultado = export_book(
            args.pdf,
            args.saida,
            formato,
            pages=args.paginas,
            enable_ocr=not args.sem_ocr,
            progress=progresso,
        )
    except (PageRangeError, ExportError, PdfOpenError, FileNotFoundError) as exc:
        sys.stderr.write(f"\nerro: {exc}\n")
        return 2
    except ImportCanceled as exc:
        sys.stderr.write(f"\n{exc}\n")
        return 130

    print(resultado.summary())
    print(f"importação: {resultado.import_report.describe_pt()}")
    print(resultado.export_result.summary())
    print(f"arquivo: {resultado.path}")
    if args.verboso and resultado.warnings:
        print("para revisão:")
        for linha in resultado.warnings:
            print(f"  {linha}")
    return 0


if __name__ == "__main__":  # pragma: no cover - console entry point
    sys.exit(main())
