"""``caissa-treinar`` — ajuste fino do Tesseract a partir de um projeto de rotulagem, sem janela.

O mesmo pipeline do botão *Treinar…* da bancada (``caissa-rotular``), para rodar num
terminal ou num job::

    caissa-treinar --project labeling --base-model BASE.traineddata
    caissa-treinar --gt labeling/ground_truth --preflight
    caissa-treinar --project labeling --document "Dvoretsky SFC4" --book --base-lang eng
    caissa-treinar --project labeling --base-lang spa --download-base

``--project`` exporta a verdade por linha antes (``ground_truth/`` dentro do projeto);
``--gt`` usa uma pasta já exportada.  ``--preflight`` só verifica: linhas por partição,
caracteres que o modelo base não codifica, e se a base parece um modelo inteiro
(``tessdata_fast``, que não aceita ajuste fino — o instalador do Windows traz esses).

``--document`` treina só com as linhas daquele livro; com ``--book`` o modelo vai para
``models/tessdata/livros/<livro>/`` e fica **registrado para o PDF** em
``models/tessdata/livros.json``: a importação desse PDF passa a usá-lo como segunda
opinião (:mod:`caissa.ocr.training.books`).  Sem ``--book``, a saída (``--out``, padrão
``models/tessdata``) fica pronta para ``--tessdata-dir``: o modelo novo, os idiomas base
copiados, ``weights.json`` com o hash, ``report.md`` e ``log.txt``.  Para medir no corpus
dourado: ``python benchmarks/bench_sol.py --tessdata-dir models/tessdata --model-prefix caissa``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from caissa.ocr.labeling import LabelProject
from caissa.ocr.labeling.export import write_ground_truth
from caissa.ocr.training import (
    BookRegistry,
    FineTuneConfig,
    TesseractFineTuner,
    TrainingToolsError,
    book_dir,
    download_base_model,
    find_training_tools,
    models_root,
    preflight,
    register_training,
)

__all__ = ["main"]

BEST_DIR = models_root().parent / "tessdata_best"


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915 - one branch per option
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--project", type=Path, help="pasta do projeto de rotulagem")
    source.add_argument("--gt", type=Path, help="pasta ground_truth já exportada")
    parser.add_argument(
        "--document", default="", help="treinar só com as linhas deste livro (nome do PDF sem .pdf)"
    )
    parser.add_argument(
        "--book",
        action="store_true",
        help="modelo do livro: sai em models/tessdata/livros/<livro>/ e fica registrado para "
        "o PDF (exige --project e --document)",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="pasta de saída (padrão models/tessdata)"
    )
    parser.add_argument("--base-lang", default="por")
    parser.add_argument(
        "--base-model",
        type=Path,
        default=None,
        help="modelo float (tessdata_best) de partida; sem ele, usa o do tessdata instalado",
    )
    parser.add_argument("--name", default="", help="nome do modelo (padrão caissa_<idioma>)")
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument(
        "--negatives",
        type=int,
        default=0,
        help="linhas de prosa do livro degradadas (foto, ruído, manchas, fax) acrescentadas "
        "ao treino, para o modelo não ver figurinas no ruído",
    )
    parser.add_argument(
        "--oversample-rare",
        type=float,
        default=0.0,
        help="repetir as linhas das peças raras até esta fração da mediana por peça (1.0 = "
        "até a mediana; 0 = desligado)",
    )
    parser.add_argument(
        "--tesseract", default=None, help="caminho do tesseract.exe, se não for achado"
    )
    parser.add_argument("--preflight", action="store_true", help="só verificar, não treinar")
    parser.add_argument(
        "--no-extend-charset",
        action="store_true",
        help="não acrescentar ao alfabeto os caracteres que a base não codifica (figurinas): "
        "as linhas com eles ficam de fora",
    )
    parser.add_argument(
        "--download-base",
        action="store_true",
        help=f"baixar tessdata_best/<idioma>.traineddata para {BEST_DIR} e usá-lo como base",
    )
    args = parser.parse_args(argv)
    if args.book and not (args.project is not None and args.document):
        parser.error("--book exige --project e --document")
    if args.download_base and args.base_model is None:
        args.base_model = download_base_model(args.base_lang, BEST_DIR, log=print)

    try:
        tools = find_training_tools(args.tesseract)
    except TrainingToolsError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    project: LabelProject | None = None
    if args.project is not None:
        project = LabelProject.load(args.project)
        if args.document and args.document not in project.documents:
            print(
                f"ERRO: o projeto não tem o livro «{args.document}»; tem: "
                + ", ".join(sorted(project.documents)),
                file=sys.stderr,
            )
            return 2
        gt_dir = project.root / "ground_truth"
        report = write_ground_truth(project, gt_dir)
        print(
            f"verdade exportada: {report.written} linhas ({report.by_partition}); "
            f"retidas por região cega: {report.withheld_blind}"
        )
    else:
        gt_dir = args.gt

    out_dir = args.out
    if args.book:
        out_dir = out_dir or book_dir(models_root(), args.document)
    out_dir = out_dir or models_root()

    config = FineTuneConfig(
        base_lang=args.base_lang,
        base_model=args.base_model,
        model_name=args.name,
        max_iterations=args.iterations,
        learning_rate=args.learning_rate,
        extend_charset=not args.no_extend_charset,
        documents=(args.document,) if args.document else (),
        negatives=args.negatives,
        oversample_rare=args.oversample_rare,
    )
    info = preflight(gt_dir, config, tools)
    print(json.dumps(info, ensure_ascii=False, indent=1))
    if "problem" in info:
        print(f"ERRO: {info['problem']}", file=sys.stderr)
        return 2
    if args.preflight:
        return 0
    if info.get("warning"):
        print(f"AVISO: {info['warning']}", file=sys.stderr)

    tuner = TesseractFineTuner(gt_dir, out_dir, config, tools=tools, log=print)
    result = tuner.run()
    print(result.markdown())
    if result.status != "trained":
        return 1
    if args.book and project is not None:
        registry = BookRegistry.default()
        book = register_training(
            registry,
            project.pdf_for(args.document),
            args.document,
            result,
            base_lang=args.base_lang,
        )
        print(
            f"registrado em {registry.path}: ao importar {book.pdf_path} o caissa usa "
            f"{', '.join(book.models)} ({book.tessdata_dir})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
