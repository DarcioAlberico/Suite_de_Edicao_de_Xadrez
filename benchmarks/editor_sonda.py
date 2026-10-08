r"""A sonda congelada do WebEngine, pelo portão — o passo H1 do Editor HTML/CSS (tarefas 3b–3d).

O `packaging/sonda_webengine.py` congelado pelo PyInstaller do `.venv-pack` (o mesmo do
`build_windows.py`): o PyQt6 do pacote no `_internal\`, o WebEngine em `runtime\webengine\`.

1. **Constrói** a sonda numa pasta da saída (`--construir`), ou usa a de `--sonda`.
2. **A instalação atômica** (tarefa 3d), pela própria sonda congelada: a instalação que cai no
   meio (`--abortar-apos`) não deixa nada em `runtime\`; a completa deixa `runtime\webengine\` e
   nada parcial.
3. **Nesta máquina:** a sonda desenha a fixture com o **Chromium**, a imagem não sai em branco, e
   toda DLL do WebEngine — as dela e as do `QtWebEngineProcess` — vem de `runtime\webengine\`.
4. **A remoção:** sem o componente, a sonda cai no **MuPDF** e desenha.
5. **A máquina limpa** (`--limpa <sonda.json>`): o registro que a sonda gravou no Windows Sandbox
   (ou numa VM sem Python), com as exigências do item 3. O usuário leva a pasta da sonda, com o
   componente instalado, à máquina limpa, roda `sonda_webengine.exe --saida <pasta>` e traz o
   `sonda.json` (o relatório, H1, diz o passo a passo).

**Sabotagem** `sonda_sem_runtime`: o item 3 roda com `runtime\webengine\` apagado. A sonda tem de
falhar nele: se desenhar com o Chromium, carregou o WebEngine de outro lugar.

Uso::

    & $PY benchmarks\editor_sonda.py --construir --saida benchmarks\reports\editor\h1\sonda `
        --limpa benchmarks\reports\editor\h1_limpa\sonda.json
    & $PY benchmarks\editor_sonda.py --sonda <pasta da sonda> --sabotar sonda_sem_runtime `
        --saida <pasta>
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
SABOTAGENS = ("sonda_sem_runtime",)
ABORTAR_APOS = 5
"""A instalação que cai depois de tantos arquivos copiados (a tarefa 3d)."""
TEMPO_LIMITE_S = 1800


def _principal() -> Path:
    comum = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False).stdout.strip()
    return Path(comum).parent if comum else RAIZ


def python_do_pacote() -> Path:
    """O Python do `.venv-pack` (o PyInstaller do `build_windows.py`), no checkout principal."""
    return _principal() / ".venv-pack" / "Scripts" / "python.exe"


def rodas_do_webengine() -> Path:
    """O `site-packages` do ambiente de medição, onde estão as rodas do WebEngine."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from editor_motores import python_do_webengine

    return python_do_webengine().parents[1] / "Lib" / "site-packages"


def construir(saida: Path) -> Path:
    r"""A sonda congelada (a pasta `sonda_webengine`, com o `.exe` e o `_internal\`)."""
    python = python_do_pacote()
    if not python.is_file():
        raise FileNotFoundError(f"o .venv-pack não existe: {python}")
    processo = subprocess.run(  # noqa: S603 - o PyInstaller do pacote, com o spec do repositório
        [str(python), "-m", "PyInstaller", str(RAIZ / "packaging" / "sonda_webengine.spec"),
         "--noconfirm", "--distpath", str(saida / "dist"), "--workpath", str(saida / "work")],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        timeout=TEMPO_LIMITE_S, cwd=RAIZ)
    (saida / "construir.log").write_text(processo.stdout + processo.stderr, encoding="utf-8")
    sonda = saida / "dist" / "sonda_webengine"
    if processo.returncode != 0 or not (sonda / "sonda_webengine.exe").is_file():
        raise RuntimeError(f"o PyInstaller falhou ({processo.returncode}): "
                           f"{(processo.stderr or processo.stdout)[-600:]}")
    return sonda


def _rodar(sonda: Path, *argumentos: str) -> tuple[int, dict[str, Any], str]:
    """A sonda congelada com os argumentos; o código, o JSON da última linha e a saída."""
    processo = subprocess.run(  # noqa: S603 - a sonda que construímos, com os nossos argumentos
        [str(sonda / "sonda_webengine.exe"), *argumentos], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=TEMPO_LIMITE_S, cwd=sonda)
    linhas = [linha for linha in processo.stdout.splitlines() if linha.strip().startswith("{")]
    dados = json.loads(linhas[-1]) if linhas else {}
    return processo.returncode, dados, processo.stdout + processo.stderr


def conferir_sonda(registro: dict[str, Any], *, motor: str) -> list[str]:
    """O que falta ao registro da sonda para o motor pedido (vazio: passou)."""
    faltas = []
    if registro.get("motor") != motor:
        faltas.append(f"desenhou com {registro.get('motor')!r}, e não com {motor!r}"
                      + (f" ({registro['erro']})" if registro.get("erro") else ""))
    if registro.get("png_em_branco", True):
        faltas.append("a imagem saiu em branco")
    if not registro.get("congelada"):
        faltas.append("não é a sonda congelada")
    if motor == "chromium":
        if not registro.get("dlls_do_webengine"):
            faltas.append("nenhuma DLL do WebEngine registrada")
        if registro.get("webengine_de_fora"):
            faltas.append(f"o WebEngine veio de fora de runtime\\webengine: "
                          f"{registro['webengine_de_fora'][:3]}")
    return faltas


def portao(sonda: Path, saida: Path, *, limpa: Path | None,
           sabotagem: str | None) -> tuple[dict[str, bool], dict[str, Any]]:
    """Os itens 2 a 5 (a instalação, esta máquina, a remoção, a máquina limpa)."""
    rodas = rodas_do_webengine()
    pacote = sonda / "_internal"
    registro: dict[str, Any] = {"sonda": str(sonda), "rodas": str(rodas), "sabotagem": sabotagem}
    exigencias: dict[str, bool] = {}
    _rodar(sonda, "--raiz", str(sonda), "--remover")
    # 2. A instalação que cai no meio não deixa nada; a completa deixa a pasta e nada parcial.
    codigo, caiu, _ = _rodar(sonda, "--raiz", str(sonda), "--instalar", str(rodas),
                             "--pacote", str(pacote), "--abortar-apos", str(ABORTAR_APOS))
    registro["instalacao_abortada"] = {"codigo": codigo, **caiu}
    codigo, feita, _ = _rodar(sonda, "--raiz", str(sonda), "--instalar", str(rodas),
                              "--pacote", str(pacote))
    registro["instalacao"] = {"codigo": codigo, **feita}
    restos = sorted(p.name for p in (sonda / "runtime").glob("webengine*"))
    exigencias[f"a instalação atômica: a que cai no meio deixa {caiu.get('restos')}, a completa "
               f"deixa {restos}"] = (caiu.get("restos") == [] and codigo == 0
                                     and restos == ["webengine"])
    # 3. Nesta máquina (a sabotagem apaga o componente antes).
    if sabotagem == "sonda_sem_runtime":
        shutil.rmtree(sonda / "runtime" / "webengine", ignore_errors=True)
    _, aqui, _ = _rodar(sonda, "--raiz", str(sonda), "--saida", str(saida / "aqui"))
    registro["aqui"] = json.loads((saida / "aqui" / "sonda.json").read_text(encoding="utf-8")) \
        if (saida / "aqui" / "sonda.json").is_file() else aqui
    faltas = conferir_sonda(registro["aqui"], motor="chromium")
    exigencias["a sonda nesta máquina: o Chromium, com o WebEngine de runtime\\webengine"
               + (f" -- {'; '.join(faltas)}" if faltas else "")] = not faltas
    # 4. A remoção devolve a sonda ao MuPDF.
    _rodar(sonda, "--raiz", str(sonda), "--remover")
    _, sem, _ = _rodar(sonda, "--raiz", str(sonda), "--saida", str(saida / "removido"))
    removido = json.loads((saida / "removido" / "sonda.json").read_text(encoding="utf-8")) \
        if (saida / "removido" / "sonda.json").is_file() else sem
    registro["removido"] = removido
    faltas = conferir_sonda(removido, motor="mupdf")
    exigencias["a remoção: a sonda cai no MuPDF e desenha"
               + (f" -- {'; '.join(faltas)}" if faltas else "")] = not faltas
    # 5. A máquina limpa: o registro que o usuário trouxe.
    if limpa is None or not limpa.is_file():
        exigencias[f"a sonda na máquina limpa: sem o registro ({limpa})"] = False
    else:
        registro["limpa"] = json.loads(limpa.read_text(encoding="utf-8"))
        faltas = conferir_sonda(registro["limpa"], motor="chromium")
        exigencias["a sonda na máquina limpa: o Chromium, com o WebEngine de runtime\\webengine"
                   + (f" -- {'; '.join(faltas)}" if faltas else "")] = not faltas
    return exigencias, registro


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--construir", action="store_true")
    parser.add_argument("--sonda", type=Path, help="a pasta da sonda já construída")
    parser.add_argument("--limpa", type=Path, help="o sonda.json da máquina limpa")
    parser.add_argument("--sabotar", choices=SABOTAGENS)
    args = parser.parse_args(argv)
    saida = args.saida if args.saida.is_absolute() else RAIZ / args.saida
    saida.mkdir(parents=True, exist_ok=True)
    if args.construir:
        sonda = construir(saida)
    elif args.sonda is not None:
        sonda = args.sonda
    else:
        parser.error("diga de onde vem a sonda: --construir ou --sonda <pasta>")
    limpa = args.limpa if args.limpa is None or args.limpa.is_absolute() else RAIZ / args.limpa
    exigencias, registro = portao(sonda, saida, limpa=limpa, sabotagem=args.sabotar)
    registro["exigencias"] = exigencias
    (saida / "sonda_portao.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    for texto, ok in exigencias.items():
        print(f"{'PASSOU' if ok else 'REPROVADO'}: {texto}")
    return 0 if all(exigencias.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
