# Origem: ChessVisionOFF_Puro/packaging/build_windows.py
# Absorvido em 2026-09-09 (F12). Alteracoes: `--medir-modulos` torna executavel a regra de
# `excludes` que la era comentario; a medicao de tamanho reporta os maiores contribuintes em
# vez de so o total; o instalador entrou (ISCC quando existe, proxy LZMA2 medido quando nao);
# a checagem de disco acontece ANTES do build, porque a SPEC R4 diz que disco e a restricao.
r"""Gera o bundle Windows do Caissa Studio e mede o que saiu (F12).

    .venv-pack\\Scripts\\python.exe packaging/build_windows.py
    .venv-pack\\Scripts\\python.exe packaging/build_windows.py --com-torch
    .venv-pack\\Scripts\\python.exe packaging/build_windows.py --medir-modulos
    .venv-pack\\Scripts\\python.exe packaging/build_windows.py --instalador

Faz cinco coisas que `pyinstaller` sozinho nao faz:

1. **Confere o disco antes.** A SPEC R4 chama disco de restricao critica desta maquina. Um
   PyInstaller que enche o disco no meio da coleta deixa uma `dist/` pela metade que parece
   pronta. Aqui o build recusa comecar sem folga, e o numero de antes e depois vai para o
   JSON de metricas -- porque um relatorio que diz "cabe" sem medir nao disse nada.
2. **Cria as pastas gravaveis ao lado do executavel.** `models/`, `data/`, `PDF/`, `PGN/`,
   `logs/`. Sem isso o primeiro `Ctrl+S` do usuario falha ao gravar num diretorio que nao
   existe -- e falha depois de ele ter corrigido um diagrama.
3. **Mede o bundle e nomeia os maiores contribuintes.** Um total sem discriminacao nao
   sustenta nenhuma decisao: "684 MB" nao diz o que cortar, "torch = 60% disto" diz.
4. **Mede o instalador.** Com o Inno Setup instalado, compila o `.iss` de verdade. Sem ele,
   comprime a `dist/` com **LZMA2 solido** -- que e literalmente o que o `installer.iss`
   pede (`Compression=lzma2/max`, `SolidCompression=yes`) -- e reporta o numero como
   **proxy medido**, dizendo que e proxy. Um teto de 150 MB afirmado sem nenhuma medicao
   seria pior que nao ter teto.
5. **Mede quais modulos estao vivos** (`--medir-modulos`), num processo limpo, e grava
   `modulos_vivos.json`. E a regra de `excludes` do tronco virada em guarda: a `caissa.spec`
   recusa montar se algum nome de `excludes` estiver ali.

Nao assina o executavel. Sem certificado de assinatura de codigo o SmartScreen avisa na
primeira execucao, e obter um e uma decisao (e uma despesa) do dono do projeto. Ver
`docs/quality/F12_REPORT.md`, secao do que nao foi verificado.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJETO = Path(__file__).resolve().parents[1]
PACOTE = PROJETO / "packaging"
SPEC = PACOTE / "caissa.spec"
TRONCO_PADRAO = Path(r"C:\Python-Chess2\ChessVisionOFF_Puro")

PASTAS_DO_USUARIO = ("models", "data", "PDF", "PGN", "logs", "runtime")
"""Nascem vazias ao lado do `.exe`, e por dois motivos diferentes.

`models/`, `data/`, `PDF/`, `PGN/` sao do **usuario**: peso baixado, rotulo corrigido,
livro, PGN exportado. Dentro do bundle sumiriam a cada reinstalacao -- e o `[InstallDelete]`
do `installer.iss` apaga `_internal` exatamente por isso, deixando estas quatro em paz.

`logs/` e do **programa**. Nasce aqui e nao so na primeira falha porque e para onde a spec
manda olhar quando a janela nao abre, e uma pasta que so existe depois do problema e uma
instrucao que nao se pode seguir."""

PASTAS_GUARDADAS = (*PASTAS_DO_USUARIO, "rotulagem")
"""O que **nao e o bundle** dentro de `dist/Caissa/`: o build nao toca nestas pastas
(`instalar_bundle` troca so `PARTES_DO_BUNDLE`) e a medicao de tamanho as exclui. Na maquina
de quem desenvolve a `dist/` e a instalacao de trabalho -- 5 GB de dataset, o `runtime/` com
a roda de torch, o projeto de rotulagem -- e reconstruir o bundle nao pode custar nada disso."""

FOLGA_MINIMA_GB = 6.0
"""Quanto o build precisa de folga para comecar. Nao e o tamanho do bundle: o PyInstaller
grava `build/` (analise, arquivos intermediarios) e `dist/` ao mesmo tempo, e a soma
transitoria passa do dobro do resultado."""

TETO_DO_INSTALADOR_MB = 150.0
"""SPEC secao 12, em uma frase: *"mantem o instalador abaixo de 150 MB"*. O build nao falha
por ultrapassar -- ele **diz**, alto, com o numero. Ver `F12_REPORT.md` para por que o
completo passa e o que seria preciso para ele caber."""

SETE_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")

logger = logging.getLogger("caissa.build")


# --------------------------------------------------------------------------- #
# medicao
# --------------------------------------------------------------------------- #
def medir_pasta(pasta: Path, *, excluir: tuple[str, ...] = ()) -> tuple[float, int]:
    """MB e numero de arquivos. `excluir`: pastas de primeiro nivel que nao contam."""
    total = 0
    quantos = 0
    for arquivo in pasta.rglob("*"):
        if arquivo.is_file() and arquivo.relative_to(pasta).parts[0] not in excluir:
            total += arquivo.stat().st_size
            quantos += 1
    return total / (1024 * 1024), quantos


def maiores_contribuintes(pasta: Path, quantos: int = 12) -> list[dict[str, Any]]:
    """As pastas de primeiro nivel dentro de `_internal/` que mais pesam, e os arquivos soltos.

    Agrupa por pasta e nao por arquivo porque a resposta util e "torch", nao
    "libtorch_cpu.dll" -- a decisao que o numero sustenta e sobre a dependencia inteira.
    """
    interno = pasta / "_internal"
    alvo = interno if interno.is_dir() else pasta
    linhas: list[dict[str, Any]] = []
    for item in alvo.iterdir():
        if item.is_dir():
            mb, n = medir_pasta(item)
            linhas.append({"nome": item.name, "mb": round(mb, 1), "arquivos": n})
        elif item.is_file() and item.stat().st_size > 4 * 1024 * 1024:
            linhas.append(
                {
                    "nome": item.name,
                    "mb": round(item.stat().st_size / (1024 * 1024), 1),
                    "arquivos": 1,
                }
            )
    linhas.sort(key=lambda linha: linha["mb"], reverse=True)
    return linhas[:quantos]


def disco_livre_gb(caminho: Path) -> float:
    """GB livres no volume de `caminho`."""
    return shutil.disk_usage(caminho).free / (1024**3)


# --------------------------------------------------------------------------- #
# --medir-modulos
# --------------------------------------------------------------------------- #
_ROTEIRO_DE_MEDICAO = r"""
import importlib, json, pkgutil, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
for p in json.loads(sys.argv[1]):
    if p not in sys.path:
        sys.path.insert(0, p)
falhas = {}
for nome in ("caissa_app", "caissa_primeira_execucao", "caissa_setup", "doctor", "app_pyqt"):
    try:
        importlib.import_module(nome)
    except BaseException as exc:
        falhas[nome] = f"{type(exc).__name__}: {exc}"
for raiz in ("chess_diagram_ocr", "caissa"):
    try:
        pacote = importlib.import_module(raiz)
    except BaseException as exc:
        falhas[raiz] = f"{type(exc).__name__}: {exc}"
        continue
    for info in pkgutil.walk_packages(pacote.__path__, raiz + "."):
        try:
            importlib.import_module(info.name)
        except BaseException as exc:
            falhas[info.name] = f"{type(exc).__name__}: {exc}"
vivos = sorted({m.split(".")[0] for m in sys.modules if not m.startswith("_")})
print(json.dumps({"vivos": vivos, "falhas": falhas}))
"""


def medir_modulos(tronco: Path) -> int:
    """Importa a arvore inteira num processo LIMPO e grava `modulos_vivos.json`.

    Processo separado de proposito. Medir `sys.modules` dentro do processo que ja importou
    metade do mundo para fazer o build mediria o build, e nao o programa -- e a lista sairia
    com `argparse`, `subprocess` e o proprio PyInstaller dentro dela.
    """
    caminhos = [
        str(PACOTE),
        str(PROJETO / "src"),
        str(PROJETO / "scripts"),
        str(tronco),
        str(tronco / "src"),
    ]
    resultado = subprocess.run(  # noqa: S603 - argv fixo
        [sys.executable, "-c", _ROTEIRO_DE_MEDICAO, json.dumps(caminhos)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(PROJETO),
    )
    if resultado.returncode != 0:
        logger.error("A medicao falhou:\n%s", resultado.stderr[-2000:])
        return 1

    dados = json.loads(resultado.stdout.strip().splitlines()[-1])
    dados["medido_em"] = datetime.now(UTC).date().isoformat()
    dados["interpretador"] = sys.version.split()[0]
    dados["comentario"] = (
        "Gerado por `build_windows.py --medir-modulos`. `vivos` sao os nomes de primeiro "
        "nivel que aparecem em sys.modules depois de importar a arvore inteira num processo "
        "limpo; `caissa.spec` recusa montar se algum deles estiver em `excludes`. `falhas` "
        "sao os modulos que nao importam neste ambiente -- normalmente por dependencia "
        "opcional ausente, o que e informacao e nao defeito."
    )
    destino = PACOTE / "modulos_vivos.json"
    destino.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(
        "Medicao gravada em %s: %d modulos vivos, %d falhas de import.",
        destino.name,
        len(dados["vivos"]),
        len(dados["falhas"]),
    )
    return 0


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
class ProgramaAbertoError(RuntimeError):
    """O `Caissa.exe` da `dist/` esta rodando: nada pode ser movido ou apagado debaixo dele."""


def programa_aberto(saida: Path) -> bool:
    """Ha um processo com o executavel desta `dist/` em execucao?

    `Get-Process` pelo PowerShell, porque o `wmic` saiu do Windows 11; a comparacao e pelo
    caminho do executavel, para um `Caissa.exe` instalado em outro lugar nao bloquear o build
    desta pasta.
    """
    if os.name != "nt":
        return False
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return False
    try:
        saida_bruta = subprocess.run(  # noqa: S603 - executavel resolvido por `which`, argumentos fixos
            [powershell, "-NoProfile", "-Command",
             "(Get-Process -Name Caissa -ErrorAction SilentlyContinue).Path"],
            capture_output=True, text=True, check=False, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    alvo = str(saida.resolve()).lower()
    return any(alvo in linha.strip().lower() for linha in saida_bruta.splitlines())


PASTA_DE_MONTAGEM = "_build"
"""`dist/_build/`: onde o PyInstaller grava, para nunca escrever em cima da `dist/Caissa/`."""

PARTES_DO_BUNDLE = ("_internal", "Caissa.exe", "CaissaPrimeiraExecucao.exe")
"""O que o build **substitui** na instalacao. Tudo o mais em `dist/Caissa/` e do usuario."""


def instalar_bundle(novo: Path, saida: Path) -> None:
    """Poe o bundle recem-montado em `saida` trocando so as `PARTES_DO_BUNDLE`.

    **O build nunca move as pastas do usuario.** A versao anterior guardava `data/`, `models/`
    e `runtime/` em `dist/_guardado/` enquanto o PyInstaller apagava a `dist/` inteira -- e um
    `rename` de `data/` falha sempre que um Explorer ou o VS Code segura a pasta, o que na
    maquina de desenvolvimento e o estado normal. Montar em `dist/_build/` e trocar so o
    `_internal/` e os dois `.exe` e o mesmo contrato do `[InstallDelete]` do `installer.iss`:
    reinstalar substitui o programa e deixa o resto em paz.
    """
    saida.mkdir(parents=True, exist_ok=True)
    for nome in PARTES_DO_BUNDLE:
        origem = novo / nome
        if not origem.exists():
            continue
        alvo = saida / nome
        if alvo.is_dir():
            shutil.rmtree(alvo)
        elif alvo.exists():
            alvo.unlink()
        origem.rename(alvo)
    sobras = [item.name for item in novo.iterdir()]
    if sobras:
        logger.warning("O PyInstaller gerou partes fora de PARTES_DO_BUNDLE, ignoradas: %s", sobras)
    shutil.rmtree(novo.parent, ignore_errors=True)


def preparar_pastas_do_usuario(saida: Path) -> None:
    """Cria as pastas gravaveis e um `LEIA-ME.txt` em `models/` explicando o vazio."""
    for nome in PASTAS_DO_USUARIO:
        (saida / nome).mkdir(parents=True, exist_ok=True)
    (saida / "models" / "LEIA-ME.txt").write_text(
        "Esta pasta esta vazia de proposito.\n\n"
        "Os pesos nao vem dentro do instalador: e assim que ele cabe abaixo de 150 MB\n"
        "(docs/SPEC.md, secao 12). Rode `CaissaPrimeiraExecucao.exe` -- ele instala cada\n"
        "arquivo e confere o SHA-256 de todos.\n\n"
        "Sem internet? O mesmo programa aceita uma pasta local:\n"
        "    CaissaPrimeiraExecucao.exe --de-pasta D:\\pendrive\\caissa-modelos\n\n"
        "O que vai aqui esta declarado em `_internal\\manifesto.json`.\n",
        encoding="utf-8",
    )
    (saida / "runtime" / "LEIA-ME.txt").write_text(
        "Esta pasta e onde o PyTorch e instalado, e tambem esta vazia de proposito.\n\n"
        "O motivo nao e so tamanho. A roda certa depende da SUA placa de video, e ela nao\n"
        "pode ser escolhida na maquina de quem monta o instalador:\n\n"
        "  * GPU NVIDIA sm_70 ou superior (a RTX 5060 e sm_120) -> roda cu128, 2,6 GB\n"
        "  * sem GPU NVIDIA utilizavel                          -> roda de CPU, 128 MB\n\n"
        "Medido em docs/quality/F4GPU_REPORT.md secao 7: 0,0903 s/diagrama com a cu128\n"
        "contra 0,5234 s/diagrama em CPU. Congelar a roda de CPU no instalador entregaria\n"
        "5,8x menos velocidade a quem tem a placa -- sem avisar.\n\n"
        "    CaissaPrimeiraExecucao.exe                        (baixa a roda certa)\n"
        "    CaissaPrimeiraExecucao.exe --rodas-de D:\\rodas    (sem internet)\n\n"
        "O que vai aqui esta declarado em `_internal\\torch_manifesto.json`, com o SHA-256\n"
        "de cada roda.\n",
        encoding="utf-8",
    )


_ROTEIRO_DO_STDLIB = r"""
import json, pathlib, sys, sysconfig, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
antes = set(sys.modules)
import torch, torch.version, torchvision  # noqa
stdlib = pathlib.Path(sysconfig.get_paths()["stdlib"]).resolve()
saida = []
for nome in sorted(set(sys.modules) - antes):
    modulo = sys.modules.get(nome)
    arquivo = getattr(modulo, "__file__", None)
    if not arquivo:
        continue
    try:
        caminho = pathlib.Path(arquivo).resolve()
    except OSError:
        continue
    if stdlib in caminho.parents and "site-packages" not in str(caminho):
        saida.append(nome)
print(json.dumps({"torch": torch.__version__, "modulos": saida}))
"""

_ROTEIRO_DAS_EXTENSOES = r"""
import importlib, json, pathlib, sys, sysconfig, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
for nome in json.loads(sys.argv[2]):
    try:
        importlib.import_module(nome)
    except Exception:
        pass
dinamica = pathlib.Path(sysconfig.get_paths()["stdlib"]).resolve() / "lib-dynload"
stdlib = pathlib.Path(sysconfig.get_paths()["stdlib"]).resolve()
dlls = stdlib.parent / "DLLs"
saida = {}
for nome, modulo in sorted(sys.modules.items()):
    arquivo = getattr(modulo, "__file__", None) or ""
    if not arquivo.endswith((".pyd", ".so")):
        continue
    try:
        caminho = pathlib.Path(arquivo).resolve()
    except OSError:
        continue
    if dlls in caminho.parents or dinamica in caminho.parents:
        saida[nome] = caminho.name
print(json.dumps(saida))
"""
"""Quais **extensoes nativas** da biblioteca padrao a arvore medida realmente carrega.

Existe porque a lista de `modulos` acima e de nomes Python, e um nome Python nao garante o
`.pyd` embaixo dele. Foi exatamente esse o defeito do ciclo 1: o bundle levou os `.py` de
`tkinter` e deixou `_tkinter.pyd` de fora; `PIL/ImageTk.py` importa `tkinter`, a linha
`from PIL import Image, ImageDraw, ImageTk` de `ui/icones.py` levantou inteira, o `except`
do modulo poe `Image = ImageDraw = None` -- e o programa perdeu **todos** os icones da fita
sem uma linha de erro. Um modulo pela metade nao falha alto; ele apaga funcionalidade.

O par (`modulos`, `extensoes_nativas`) fecha os dois lados: o primeiro entra em
`hiddenimports`, o segundo e conferido no bundle pronto por `conferir_extensoes_nativas()`.
"""


def medir_stdlib_do_torch(fontes: list[Path]) -> int:
    r"""Mede QUAIS modulos da biblioteca padrao o torch importa, e grava a medicao.

    **Este arquivo existe por causa de um defeito que so aparece depois de empacotar**, e que
    custou tres builds para ser localizado.

    Com o torch fora do bundle, o PyInstaller passa a nao ver nenhum `import torch` -- e por
    isso nao coleta os modulos da **biblioteca padrao** que so o torch usa. O bundle sai sem
    `uuid`, sem `unittest.mock`, sem `asyncio.windows_events`. O torch instalado depois em
    `runtime/` encontra o proprio pacote e nao encontra o Python embaixo dele.

    O sintoma nao e um `ImportError` legivel. Medido em 2026-09-09, com a sonda
    `CaissaPrimeiraExecucao.exe --sondar-torch`:

        -> filelock
           FALHOU ModuleNotFoundError: No module named 'uuid'
        -> torch.version
           FALHOU ImportError: cannot import name 'mock' from 'unittest'
        -> torch._C
        EXIT = -1073740791          (0xC0000409, STATUS_STACK_BUFFER_OVERRUN)

    Ou seja: os dois primeiros degraus falham com mensagens que ninguem liga ao torch, e o
    terceiro **derruba o processo sem traceback**. Uma extensao nativa carregada com metade do
    seu pacote Python inicializado nao levanta excecao: ela morre.

    A medicao roda num processo limpo, com o torch de cada fonte, e a `caissa.spec` pede em
    `hiddenimports` a UNIAO do que sair. E a mesma disciplina de `modulos_vivos.json`: uma
    regra que o build confere em vez de um comentario que alguem lembra.
    """
    uniao: set[str] = set()
    versoes: dict[str, str] = {}
    for fonte in fontes:
        if not (fonte / "torch" / "__init__.py").is_file():
            logger.info("Sem torch em %s; pulando.", fonte)
            continue
        resultado = subprocess.run(  # noqa: S603 - argv fixo
            [sys.executable, "-c", _ROTEIRO_DO_STDLIB, str(fonte)],
            capture_output=True,
            text=True,
            check=False,
        )
        if resultado.returncode != 0:
            logger.error("A medicao em %s falhou:\n%s", fonte, resultado.stderr[-1500:])
            continue
        dados = json.loads(resultado.stdout.strip().splitlines()[-1])
        versoes[str(fonte)] = dados["torch"]
        uniao |= set(dados["modulos"])
        logger.info("%s (torch %s): %d modulos.", fonte, dados["torch"], len(dados["modulos"]))

    if not uniao:
        logger.error("Nenhuma fonte de torch utilizavel. Nada foi medido, nada foi gravado.")
        return 1

    # As extensoes nativas, medidas a partir da uniao acima MAIS os dois nomes que a
    # `caissa.spec` pede a mao pela janela (`tkinter` e `PIL.ImageTk`). Sao esses dois que
    # levaram os icones embora no ciclo 1, e um deles (`_tkinter.pyd`) nao aparece em nenhum
    # import do torch -- so seria medido se alguem o pedisse.
    alvos = sorted(uniao | {"tkinter", "PIL.ImageTk", "sqlite3", "ssl", "ctypes", "decimal"})
    extensoes: dict[str, str] = {}
    for fonte in fontes:
        if not (fonte / "torch" / "__init__.py").is_file():
            continue
        resultado = subprocess.run(  # noqa: S603 - argv fixo
            [sys.executable, "-c", _ROTEIRO_DAS_EXTENSOES, str(fonte), json.dumps(alvos)],
            capture_output=True,
            text=True,
            check=False,
        )
        if resultado.returncode != 0:
            logger.error("A medicao de extensoes em %s falhou:\n%s", fonte, resultado.stderr[-800:])
            continue
        extensoes |= json.loads(resultado.stdout.strip().splitlines()[-1])
    if not extensoes:
        logger.error(
            "Nenhuma extensao nativa medida. Sem essa lista o build nao tem como reprovar um "
            "bundle sem `_tkinter.pyd`, que foi o defeito do ciclo 1. Nada foi gravado."
        )
        return 1
    logger.info("%d extensoes nativas da biblioteca padrao medidas.", len(extensoes))

    destino = PACOTE / "stdlib_do_torch.json"
    destino.write_text(
        json.dumps(
            {
                "medido_em": datetime.now(UTC).date().isoformat(),
                "interpretador": sys.version.split()[0],
                "fontes": versoes,
                "comentario": (
                    "Modulos da biblioteca padrao que o torch importa e que o PyInstaller NAO "
                    "coleta sozinho quando o torch esta fora do bundle. A caissa.spec os pede "
                    "em hiddenimports. `extensoes_nativas` mapeia nome de modulo -> .pyd, e "
                    "`conferir_extensoes_nativas()` reprova o build que sair sem algum deles. "
                    "Regenerar: build_windows.py --medir-stdlib-do-torch."
                ),
                "modulos": sorted(uniao),
                "extensoes_nativas": dict(sorted(extensoes.items())),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("Uniao de %d modulos gravada em %s.", len(uniao), destino.name)
    return 0


def conferir_extensoes_nativas(saida: Path) -> int:
    r"""Reprova o bundle que sair sem alguma extensao nativa da biblioteca padrao medida.

    **O ponto do ciclo 2 que a lista de `hiddenimports` sozinha nao cobre.**

    Um nome em `hiddenimports` faz o PyInstaller *tentar* coletar. Ele nao garante que a
    extensao nativa correspondente chegou -- e quando nao chega, ninguem reclama. Foi assim
    que o ciclo 1 perdeu **todos os icones da fita**: `_tkinter.pyd` ficou de fora, os `.py`
    de `tkinter` entraram, `PIL/ImageTk.py` levantou `ImportError`, e como `ui/icones.py`
    importa `Image, ImageDraw, ImageTk` na mesma linha, o `except` zerou os tres. Build
    verde, instalador verde, janela sem icones.

    A regra aqui e a mesma de `modulos_vivos.json` e de `binarios_do_torchvision`: a coleta
    vazia e silenciosa e o defeito, entao o build **falha alto** em vez de sair pela metade.

    Devolve 0 quando tudo esta la, 1 quando falta alguma, 0 com aviso quando a medicao ainda
    nao existe (a lista e regenerada por `--medir-stdlib-do-torch`; um build sem ela e uma
    lacuna avisada, nao um build reprovado).
    """
    medicao = PACOTE / "stdlib_do_torch.json"
    if not medicao.exists():
        logger.warning("%s nao existe; nao ha o que conferir.", medicao.name)
        return 0
    dados = json.loads(medicao.read_text(encoding="utf-8"))
    exigidas: dict[str, str] = dados.get("extensoes_nativas") or {}
    if not exigidas:
        logger.warning(
            "%s nao tem `extensoes_nativas`. Rode `--medir-stdlib-do-torch` para que o build "
            "possa reprovar um bundle sem `_tkinter.pyd`.",
            medicao.name,
        )
        return 0

    interno = saida / "_internal"
    presentes = {p.name for p in interno.glob("*.pyd")}
    faltando = {mod: pyd for mod, pyd in exigidas.items() if pyd not in presentes}
    if faltando:
        logger.error(
            "O bundle saiu sem %d extensao(oes) nativa(s) da biblioteca padrao que a medicao "
            "de %s exige:",
            len(faltando),
            dados.get("medido_em", "?"),
        )
        for mod_, pyd in sorted(faltando.items()):
            logger.error("  %-24s -> %s AUSENTE em %s", mod_, pyd, interno)
        logger.error(
            "Isto NAO e cosmetico: um modulo pela metade nao levanta onde falta -- ele levanta "
            "em quem o importa. Foi assim que `_tkinter.pyd` apagou todos os icones da fita no "
            "ciclo 1. Confira `hiddenimports` na caissa.spec antes de distribuir."
        )
        return 1
    logger.info("As %d extensoes nativas da biblioteca padrao estao em _internal/.", len(exigidas))
    return 0


def preparar_licencas_e_pecas(*, com_torch: bool) -> int:
    """Gera `licenses/` e `assets/piece_images/` antes do build, e falha se nao der.

    As duas coisas sao **pre-condicao de legalidade**, e nao passos opcionais:

    * sem `licenses/`, o pacote viola a AGPL-3.0 secao 4 (o texto tem de acompanhar a
      distribuicao) e as clausulas de aviso de BSD/MIT/Apache. O ciclo 1 terminou com essa
      lacuna aberta e a frase *"o build e para uso proprio"*;
    * sem `assets/piece_images/` gerada aqui, a `caissa.spec` cairia para as pecas do tronco
      -- que `PECAS_PROCEDENCIA.md` mede como a mesma arte de um conjunto declarado *"All
      rights reserved"*.

    Rodar isso **dentro** do build, e nao como um passo separado que alguem lembra de fazer,
    e o que impede um pacote legalmente incompleto de existir.
    """
    if not (PACOTE / "assets" / "piece_images" / "wk.png").exists():
        logger.info("Gerando as pecas de licenca conhecida (cburnett)...")
        processo = subprocess.run(  # noqa: S603 - argv fixo
            [sys.executable, str(PACOTE / "gerar_pecas_livres.py")], check=False
        )
        if processo.returncode != 0:
            logger.error("gerar_pecas_livres.py falhou com codigo %d.", processo.returncode)
            return processo.returncode

    logger.info("Coletando os textos de licenca...")
    bundle = PROJETO / "dist" / ("Caissa-com-torch" if com_torch else "Caissa")
    argumentos = [sys.executable, str(PACOTE / "coletar_licencas.py")]
    if bundle.exists():
        # Com um bundle anterior no disco, o inventario e medido CONTRA ELE -- que e a unica
        # forma de a lista significar "o que sai" e nao "o que o venv tem".
        argumentos += ["--bundle", str(bundle)]
    processo = subprocess.run(argumentos, check=False)  # noqa: S603 - argv fixo
    if processo.returncode != 0:
        logger.error(
            "coletar_licencas.py falhou com codigo %d. O build para: um pacote sem os textos "
            "de licenca nao pode ser entregue a ninguem.",
            processo.returncode,
        )
        return processo.returncode
    return 0


def conferir_licencas_do_bundle(saida: Path) -> int:
    r"""Reconfere o inventario de licencas contra o bundle **que acabou de sair**.

    **Um defeito de ordem, encontrado em 2026-09-09 alternando as duas variantes.**

    `preparar_licencas_e_pecas()` roda ANTES do PyInstaller -- e tem de rodar, porque os
    textos entram no bundle como `datas`. Mas `coletar_licencas._topos_do_toc()` le os `.toc`
    de `build/`, que naquele instante ainda sao os do build **anterior**. Depois de montar a
    variante `com-torch` e em seguida a padrao, o inventario da padrao saiu dizendo:

        torch | bundle | ['functorch', 'torch', 'torchgen']

    O bundle padrao nao leva torch. O texto da licenca estava la (o portao de `sem_texto`
    segurou), mas o documento **afirmava algo falso sobre o que o pacote contem** -- e um
    inventario de licenca que erra o que esta dentro e um inventario que ninguem pode usar.

    O conserto e reconferir depois. Com o `.toc` fresco, a coleta e refeita e comparada com a
    copia que viajou dentro do bundle; divergindo, o build **falha** e pede outro. Na segunda
    passagem o `.toc` ja e o certo e converge. Buildar a mesma variante duas vezes seguidas
    nao dispara nada -- so a troca de variante, que e exatamente quando o erro acontece.
    """
    dentro = saida / "_internal" / "licenses" / "INDICE.json"
    if not dentro.is_file():
        logger.error(
            "%s nao existe. O bundle saiu sem o inventario de licencas -- ele nao pode ser "
            "distribuido assim (AGPL-3.0 secao 4).",
            dentro,
        )
        return 1

    sys.path.insert(0, str(PACOTE))
    import coletar_licencas as col

    novo = col.coletar(saida)
    if novo["sem_texto"]:
        logger.error("Dependencias distribuidas sem texto de licenca: %s", novo["sem_texto"])
        return 1

    def _mapa(indice: dict[str, Any]) -> dict[str, str]:
        return {d["distribuicao"]: d["origem"] for d in indice["distribuicoes"]}

    antes = _mapa(json.loads(dentro.read_text(encoding="utf-8")))
    depois = _mapa(novo)
    if antes != depois:
        divergentes = sorted(
            set(antes) | set(depois),
            key=str.lower,
        )
        logger.error(
            "O inventario que viajou dentro do bundle foi gerado com o `.toc` do build "
            "ANTERIOR e nao descreve este pacote:"
        )
        for nome in divergentes:
            a, d = antes.get(nome), depois.get(nome)
            if a != d:
                logger.error("  %-24s dentro do bundle: %-28s medido agora: %s", nome, a, d)
        logger.error(
            "`packaging/licenses/` acabou de ser regravado com a medicao certa. "
            "Rode o build de novo -- a segunda passagem ja sai coerente."
        )
        return 1

    logger.info("Inventario de licencas confere com o bundle: %d distribuicoes.", len(depois))
    return 0


def build(  # noqa: PLR0911 - oito saidas, e cada uma e um portao com motivo proprio
    *, com_torch: bool, limpar: bool, tronco: Path
) -> tuple[int, Path | None]:
    """Roda o PyInstaller. Devolve `(codigo, pasta_de_saida)`.

    Sao oito `return` e nenhum e redundante: spec ausente, disco insuficiente, licencas ou
    pecas que nao geraram, PyInstaller que falhou, `dist/` que nao apareceu, extensao nativa
    faltando, inventario de licenca incoerente, e o caminho feliz. Espremer isso num codigo
    de erro so faria o build dizer "falhou" onde hoje ele diz o que fazer.
    """
    if not SPEC.exists():
        logger.error("Spec nao encontrada em %s.", SPEC)
        return 2, None

    livre = disco_livre_gb(PROJETO)
    logger.info("Disco livre antes do build: %.2f GB.", livre)
    if livre < FOLGA_MINIMA_GB:
        logger.error(
            "So %.2f GB livres; o build precisa de ~%.0f GB de folga (SPEC R4). "
            "Nao vou comecar para nao deixar uma dist/ pela metade.",
            livre,
            FOLGA_MINIMA_GB,
        )
        return 2, None

    codigo = preparar_licencas_e_pecas(com_torch=com_torch)
    if codigo != 0:
        return codigo, None

    ambiente = dict(os.environ)
    ambiente["CAISSA_COM_TORCH"] = "1" if com_torch else "0"
    ambiente["CAISSA_TRONCO"] = str(tronco)

    montagem = PROJETO / "dist" / PASTA_DE_MONTAGEM
    comando = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm",
               "--distpath", str(montagem)]
    if limpar:
        comando.append("--clean")
    logger.info(
        "Rodando: %s (CAISSA_COM_TORCH=%s)", " ".join(comando), ambiente["CAISSA_COM_TORCH"]
    )

    nome = "Caissa-com-torch" if com_torch else "Caissa"
    saida = PROJETO / "dist" / nome
    if programa_aberto(saida):
        logger.error(
            "%s esta aberto. Feche o programa antes de reconstruir: o build troca o _internal/ "
            "e os .exe que ele esta usando.", saida / "Caissa.exe",
        )
        return 2, None
    shutil.rmtree(montagem, ignore_errors=True)

    resultado = subprocess.run(comando, cwd=str(PROJETO), env=ambiente, check=False)  # noqa: S603
    if resultado.returncode != 0:
        logger.error("PyInstaller falhou com codigo %d.", resultado.returncode)
        return resultado.returncode, None

    novo = montagem / nome
    if not novo.exists():
        logger.error("O build terminou sem erro mas %s nao existe.", novo)
        return 1, None
    instalar_bundle(novo, saida)
    logger.info("Bundle instalado em %s (so %s trocados).", saida, ", ".join(PARTES_DO_BUNDLE))

    codigo = conferir_extensoes_nativas(saida)
    if codigo != 0:
        return codigo, saida

    codigo = conferir_licencas_do_bundle(saida)
    if codigo != 0:
        return codigo, saida

    preparar_pastas_do_usuario(saida)
    return 0, saida


# --------------------------------------------------------------------------- #
# instalador
# --------------------------------------------------------------------------- #
def achar_iscc() -> Path | None:
    """O compilador do Inno Setup, se estiver nesta maquina."""
    do_path = shutil.which("ISCC") or shutil.which("iscc")
    if do_path:
        return Path(do_path)
    for base in (r"C:\Program Files (x86)\Inno Setup 6", r"C:\Program Files\Inno Setup 6"):
        candidato = Path(base) / "ISCC.exe"
        if candidato.exists():
            return candidato
    return None


def versao_do_projeto() -> str:
    """Le `version` do `pyproject.toml`. Um instalador com versao inventada nao atualiza."""
    texto = (PROJETO / "pyproject.toml").read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.strip().startswith("version"):
            return linha.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


def compilar_instalador(saida: Path, *, com_torch: bool) -> dict[str, Any]:
    """Compila o `.iss` com o ISCC; sem ele, mede o proxy LZMA2 e diz que e proxy."""
    versao = versao_do_projeto()
    iss = PACOTE / "installer.iss"
    iscc = achar_iscc()

    if iscc is not None:
        variante = "com-torch" if com_torch else "padrao"
        comando = [
            str(iscc),
            str(iss),
            f"/DAppVersion={versao}",
            f"/DVariant={variante}",
            f"/DSourceDir={saida}",
            f"/DOutputDir={PROJETO / 'dist'}",
        ]
        logger.info("Compilando o instalador: %s", " ".join(comando))
        processo = subprocess.run(comando, capture_output=True, text=True, check=False)  # noqa: S603
        if processo.returncode != 0:
            logger.error("ISCC falhou:\n%s", (processo.stdout + processo.stderr)[-2000:])
            return {"tipo": "iscc", "ok": False, "erro": processo.stderr[-500:]}
        sufixo = "com-torch" if com_torch else "setup"
        alvo = PROJETO / "dist" / f"Caissa-{versao}-{sufixo}-setup.exe"
        mb = alvo.stat().st_size / (1024 * 1024) if alvo.exists() else 0.0
        return {"tipo": "iscc", "ok": alvo.exists(), "arquivo": str(alvo), "mb": round(mb, 1)}

    if not SETE_ZIP.exists():
        logger.warning(
            "Nem Inno Setup nem 7-Zip nesta maquina: o tamanho do instalador NAO foi medido. "
            "Um teto afirmado sem medicao nao vale nada; o relatorio vai dizer isso."
        )
        return {"tipo": "nenhum", "ok": False, "erro": "sem ISCC e sem 7z"}

    # Proxy: exatamente a compressao que o installer.iss pede (lzma2/max, solido).
    alvo = PROJETO / "dist" / f"caissa-{versao}-{'com-torch' if com_torch else 'padrao'}-proxy.7z"
    alvo.unlink(missing_ok=True)
    comando = [
        str(SETE_ZIP),
        "a",
        "-t7z",
        "-m0=lzma2",
        "-mx=9",
        "-ms=on",
        "-mmt=on",
        str(alvo),
        str(saida / "*"),
    ]
    logger.info("Inno Setup ausente. Medindo o proxy LZMA2 solido: %s", alvo.name)
    processo = subprocess.run(comando, capture_output=True, text=True, check=False)  # noqa: S603
    if processo.returncode != 0 or not alvo.exists():
        logger.error("7z falhou:\n%s", (processo.stdout + processo.stderr)[-1500:])
        return {"tipo": "proxy", "ok": False, "erro": processo.stdout[-500:]}
    mb = alvo.stat().st_size / (1024 * 1024)
    return {
        "tipo": "proxy-lzma2",
        "ok": True,
        "arquivo": str(alvo),
        "mb": round(mb, 1),
        "nota": (
            "PROXY MEDIDO, nao o instalador. O Inno Setup nao esta nesta maquina. "
            "A compressao e a mesma que installer.iss pede (lzma2/max, solido); o setup.exe "
            "real acrescenta o stub do Inno (~1,2 MB) e os arquivos de idioma."
        ),
    }


# --------------------------------------------------------------------------- #
# relatorio
# --------------------------------------------------------------------------- #
def gravar_metricas(
    saida: Path, *, com_torch: bool, instalador: dict[str, Any], livre_antes: float
) -> dict[str, Any]:
    """Grava `packaging/bundle.json`. Cada numero saiu do disco nesta execucao.

    Mede o que **se distribui**: as pastas do usuario (dataset, runtime, pesos) voltam para a
    `dist/` no fim do build e nao sao o bundle -- sem excluir, um build na maquina de
    desenvolvimento mediria 10 GB onde o instalador leva 297 MB.
    """
    mb, arquivos = medir_pasta(saida, excluir=PASTAS_GUARDADAS)
    dados = {
        "variante": "com-torch" if com_torch else "padrao",
        "nome": saida.name,
        "mb": round(mb, 1),
        "arquivos": arquivos,
        "maiores": maiores_contribuintes(saida),
        "instalador": instalador,
        "teto_do_instalador_mb": TETO_DO_INSTALADOR_MB,
        "disco_livre_gb_antes": round(livre_antes, 2),
        "disco_livre_gb_depois": round(disco_livre_gb(PROJETO), 2),
        "data": datetime.now(UTC).date().isoformat(),
        "interpretador": sys.version.split()[0],
    }
    # Um arquivo por variante. Um `bundle.json` unico faria a segunda medicao apagar a
    # primeira, e a comparacao completo-contra-leve -- que e o unico jeito de saber quanto o
    # torch custa -- deixaria de existir no disco no instante em que fosse feita.
    nome = "bundle-com-torch.json" if com_torch else "bundle.json"
    (PACOTE / nome).write_text(
        json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return dados


def relatar(dados: dict[str, Any]) -> None:
    """Imprime o que interessa, com os maiores contribuintes nomeados."""
    logger.info("-" * 70)
    logger.info(
        "Bundle %s: %.1f MB em %d arquivos (%s).",
        dados["nome"],
        dados["mb"],
        dados["arquivos"],
        dados["variante"],
    )
    logger.info("Maiores contribuintes:")
    for linha in dados["maiores"]:
        fatia = 100.0 * linha["mb"] / dados["mb"] if dados["mb"] else 0.0
        logger.info("  %8.1f MB  %5.1f%%  %s", linha["mb"], fatia, linha["nome"])

    inst = dados["instalador"]
    if inst.get("ok"):
        marca = "OK" if inst["mb"] <= TETO_DO_INSTALADOR_MB else "ACIMA DO TETO"
        logger.info(
            "Instalador (%s): %.1f MB - teto da SPEC secao 12 e %.0f MB -> %s",
            inst["tipo"],
            inst["mb"],
            TETO_DO_INSTALADOR_MB,
            marca,
        )
        if inst.get("nota"):
            logger.info("  %s", inst["nota"])
    else:
        logger.warning("Instalador NAO medido: %s", inst.get("erro", "?"))

    logger.info(
        "Disco: %.2f GB livres antes, %.2f GB depois.",
        dados["disco_livre_gb_antes"],
        dados["disco_livre_gb_depois"],
    )
    logger.info("-" * 70)


def construir_analisador() -> argparse.ArgumentParser:
    """Argumentos do build."""
    analisador = argparse.ArgumentParser(description="Build Windows do Caissa Studio (F12).")
    analisador.add_argument(
        "--com-torch",
        action="store_true",
        help="bundle de MEDICAO, com torch congelado dentro (nao e o que se distribui)",
    )
    analisador.add_argument("--limpar", action="store_true", help="passa --clean ao PyInstaller")
    analisador.add_argument(
        "--instalador", action="store_true", help="compila (ou mede o proxy do) instalador"
    )
    analisador.add_argument(
        "--medir-modulos",
        action="store_true",
        help="so regrava modulos_vivos.json e sai",
    )
    analisador.add_argument(
        "--medir-stdlib-do-torch",
        action="store_true",
        help="so regrava stdlib_do_torch.json e sai (ver a docstring da funcao)",
    )
    analisador.add_argument(
        "--tronco", type=Path, default=TRONCO_PADRAO, help="checkout de ChessVisionOFF_Puro"
    )
    return analisador


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = construir_analisador().parse_args(argv)

    if args.medir_modulos:
        return medir_modulos(args.tronco)

    if args.medir_stdlib_do_torch:
        return medir_stdlib_do_torch(
            [
                PROJETO / "dist" / "Caissa" / "runtime",
                PROJETO / ".venv" / "Lib" / "site-packages",
                PROJETO / ".venv-pack" / "Lib" / "site-packages",
            ]
        )

    livre_antes = disco_livre_gb(PROJETO)
    codigo, saida = build(com_torch=args.com_torch, limpar=args.limpar, tronco=args.tronco)
    if codigo != 0 or saida is None:
        return codigo

    instalador: dict[str, Any] = {"tipo": "nao-pedido", "ok": False}
    if args.instalador:
        instalador = compilar_instalador(saida, com_torch=args.com_torch)

    dados = gravar_metricas(
        saida, com_torch=args.com_torch, instalador=instalador, livre_antes=livre_antes
    )
    relatar(dados)
    logger.info("Zipe %s inteira, ou instale pelo setup. Roda sem Python na maquina.", saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
