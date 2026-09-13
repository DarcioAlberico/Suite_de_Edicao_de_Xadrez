"""Ajuste fino do Tesseract a partir de um projeto de rotulagem, sem janela.

O mesmo pipeline do botão *Treinar…* de ``tools/rotular.py`` (``caissa.ocr.training``),
para rodar num terminal ou num job::

    python tools/treinar_tesseract.py --project labeling --base-model BASE.traineddata
    python tools/treinar_tesseract.py --gt labeling/ground_truth --preflight
    python tools/treinar_tesseract.py --gt labeling/ground_truth --base-lang eng --iterations 4000
    python tools/treinar_tesseract.py --project labeling --base-lang spa --download-base

``--project`` exporta a verdade por linha antes (``ground_truth/`` dentro do projeto);
``--gt`` usa uma pasta já exportada.  ``--preflight`` só verifica: linhas por partição,
caracteres que o modelo base não codifica, e se a base parece um modelo inteiro
(``tessdata_fast``, que não aceita ajuste fino — o instalador do Windows traz esses).

A saída (``--out``, padrão ``models/tessdata``) fica pronta para ``--tessdata-dir``:
o modelo novo, os idiomas base copiados, ``weights.json`` com o hash, ``report.md`` e
``log.txt``.  Para medir no corpus dourado: ``python benchmarks/bench_sol.py
--tessdata-dir models/tessdata --model-prefix caissa``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from caissa.ocr.labeling import LabelProject  # noqa: E402
from caissa.ocr.labeling.export import write_ground_truth  # noqa: E402
from caissa.ocr.training import (  # noqa: E402
    FineTuneConfig,
    TesseractFineTuner,
    TrainingToolsError,
    download_base_model,
    find_training_tools,
    preflight,
)

BEST_DIR = REPO_ROOT / "models" / "tessdata_best"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--project", type=Path, help="pasta do projeto de rotulagem")
    source.add_argument("--gt", type=Path, help="pasta ground_truth já exportada")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "models" / "tessdata")
    parser.add_argument("--base-lang", default="por")
    parser.add_argument(
        "--base-model",
        type=Path,
        default=None,
        help="modelo float (tessdata_best) de partida; sem ele, usa o do tessdata instalado",
    )
    parser.add_argument("--name", default="", help="nome do modelo (padrão caissa_<idioma>)")
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--learning-rate", type=float, default=0.0001)
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
    if args.download_base and args.base_model is None:
        args.base_model = download_base_model(args.base_lang, BEST_DIR, log=print)

    try:
        tools = find_training_tools(args.tesseract)
    except TrainingToolsError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    if args.project is not None:
        project = LabelProject.load(args.project)
        gt_dir = project.root / "ground_truth"
        report = write_ground_truth(project, gt_dir)
        print(
            f"verdade exportada: {report.written} linhas ({report.by_partition}); "
            f"retidas por região cega: {report.withheld_blind}"
        )
    else:
        gt_dir = args.gt

    config = FineTuneConfig(
        base_lang=args.base_lang,
        base_model=args.base_model,
        model_name=args.name,
        max_iterations=args.iterations,
        learning_rate=args.learning_rate,
        extend_charset=not args.no_extend_charset,
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

    tuner = TesseractFineTuner(gt_dir, args.out, config, tools=tools, log=print)
    result = tuner.run()
    print(result.markdown())
    return 0 if result.status == "trained" else 1


if __name__ == "__main__":
    sys.exit(main())
