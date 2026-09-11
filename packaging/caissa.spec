# Origem: ChessVisionOFF_Puro/packaging/cvoff.spec
# Absorvido em 2026-09-09 (F12). Alteracoes: dois executaveis em vez de um (a janela e o
# assistente de primeira execucao); duas variantes por CAISSA_LIGHT; `excludes` conferida
# contra uma medicao em disco em vez de contra a memoria de quem escreve; os dois lexicos de
# licenca nao apurada saem do bundle por decisao de licenciamento e nao de tamanho.
"""Bundle Windows do Caissa Studio (F12).

    .venv-pack\\Scripts\\python.exe packaging/build_windows.py

Sai em `dist/Caissa/`. A pasta roda numa maquina Windows sem Python.

---------------------------------------------------------------------------------------
O QUE ESTE BUNDLE E

A janela do produto e a do tronco (`ChessVisionOFF_Puro/app_pyqt.py`), pela ADR-0009: ha
~19.600 linhas de interface PyQt6 la e a disciplina `ui/` (decide) contra `qt/` (pinta)
mantem a migracao para PySide6 mecanica. O que a suite acrescenta -- `src/caissa/`, o
Document IR, os exportadores, o indice, a notacao -- viaja no mesmo arquivo compilado e
fica importavel de dentro da janela.

`--onedir` E NAO `--onefile`, e a razao e a mesma do tronco
-----------------------------------------------------------
`--onefile` extrai o bundle inteiro para `%TEMP%` **a cada execucao**. Sao centenas de MB
de descompressao antes de a janela aparecer, toda vez -- e o disco cheio se o antivirus
segurar a pasta temporaria. A SPEC R4 diz que disco e a restricao critica desta maquina;
gastar o dobro do bundle em `%TEMP%` a cada clique e exatamente o que R4 proibe.
`--onedir` paga a descompressao uma vez, na instalacao.

O TORCH NAO ESTA AQUI DENTRO (ciclo 2)
--------------------------------------
`CAISSA_COM_TORCH=1` monta a variante de **medicao**, com torch congelado dentro. O padrao --
e o que se distribui -- **nao leva torch**.

A razao esta medida. O ciclo 1 empacotou o torch de CPU para caber nos 150 MB da SPEC secao
12 (e mesmo assim saiu em 169,3 MB). O `F4GPU_REPORT.md` secao 7 mede o preco disso: **0,0903
s/diagrama em GPU contra 0,5234 em CPU**. Congelar a roda de CPU no instalador entrega 5,8x
menos velocidade a quem tem uma RTX -- em silencio.

Entao o torch segue o caminho que os pesos ja seguiam: sai do instalador e chega na primeira
execucao, com SHA-256, caminho offline e a roda **certa para a GPU que estiver do outro
lado** (`caissa_torch.py`). Ele e instalado em `<pasta do exe>/runtime/`, e o
`runtime_hook_torch.py` poe essa pasta em `sys.path` antes de qualquer import.

* **padrao** (`Caissa`) -- o produto. Sem torch dentro; com o assistente que o instala.
* **`CAISSA_COM_TORCH=1`** (`Caissa-com-torch`) -- existe **so para medir** quanto o torch
  custaria congelado, e o `F12_REPORT_C2.md` publica os dois numeros lado a lado. Nao e uma
  variante de distribuicao.

O que ainda nao esta resolvido, e nao e desta frente: a janela do tronco **nao abre** sem
torch, porque a cadeia `qt/janela.py -> qt/campo.py -> field_eval.py -> checkpoint.py`
importa torch no topo do modulo (medido em 2026-09-09; sao 49 modulos e 9 deles em `qt/`).
Na pratica isso significa que abrir `Caissa.exe` **antes** de rodar o assistente da um codigo
7 com traceback em `logs/`, em vez de uma janela degradada. O conserto exato esta escrito em
`packaging/pendencias/0001-torch-fora-do-escopo-de-modulo.patch` e depende da F9, que e a dona
de `qt/`.

O QUE **NAO** VAI DENTRO, DE PROPOSITO
--------------------------------------
- **Os pesos** (`models/*.pt`, ~11,5 MB). Ficam **ao lado** do executavel e chegam pelo
  assistente, com SHA-256. E o que a SPEC secao 12 manda, e tem um segundo motivo que o
  tronco ja documentou: um modelo dentro do `.exe` e o unico que o usuario nao consegue
  trocar depois de retreinar.
- **`idioma.txt.gz` e `nomes.txt.gz`** (1,12 MB somados). **Saem por licenca, nao por
  tamanho.** `ChessVisionOFF_Puro/assets/lexico/PROCEDENCIA.md` registra que os dois vem de
  arquivos sem cabecalho, licenca nem README, e que parte de `nomes.txt.gz` e um extrato do
  indice de jogadores da MegaDatabase da ChessBase -- base comercial. O custo de tirar esta
  medido no proprio PROCEDENCIA.md: **nenhum caractere muda** no texto entregue em 40
  paginas de 11 livros. `acervo.txt.gz` fica, porque e material derivado do acervo do dono
  do projeto. Ver LICENSING.md.
- **O LLM.** `docs/quality/F11_REPORT.md` mediu Gemma 4 E4B com especificidade **0,000** na
  verificacao de diagramas: ele aprova tudo. Empacotar gigabytes de pesos para um veredito
  que nao discrimina seria pagar o preco inteiro por informacao nenhuma.
- **`data/`, `PDF/`, `PGN/`, `logs/`** -- do usuario e do programa, nascem ao lado do `.exe`.
- **Stockfish** -- opcional e externo desde o tronco; `engine.find_engine` o procura.

A REGRA DE `excludes`, E O QUE MUDA AQUI
-----------------------------------------
O tronco escreveu a regra: *"so entra em `excludes` o que NAO aparece em `sys.modules`
depois de importar o pacote"*. Ela e certa e era um comentario -- e um comentario nao
impede ninguem de excluir um modulo vivo e descobrir na maquina do usuario.

Aqui ela e **executavel**. `build_windows.py --medir-modulos` importa a arvore inteira num
processo limpo e grava `packaging/modulos_vivos.json`; este arquivo le esse JSON e
**recusa a montar o bundle** se algum nome de `excludes` estiver na lista de vivos. A
medicao e datada e versionada, e `tests/integration/test_packaging.py` reconfere.
"""

import json
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PACOTE = Path(SPECPATH).resolve()  # noqa: F821 - SPECPATH e a PASTA da spec, nao o arquivo
PROJETO = PACOTE.parent
TRONCO = Path(os.environ.get("CAISSA_TRONCO", r"C:\Python-Chess2\ChessVisionOFF_Puro"))

COM_TORCH = os.environ.get("CAISSA_COM_TORCH", "").strip() in {"1", "true", "sim", "yes"}
"""O bundle de MEDICAO leva torch dentro; o de distribuicao nao. O padrao e o que se
distribui, porque um padrao que ninguem entrega e um padrao que ninguem testa."""

SEM_TORCH = not COM_TORCH
NOME = "Caissa-com-torch" if COM_TORCH else "Caissa"

if not (TRONCO / "app_pyqt.py").exists():
    raise SystemExit(
        f"O frontend do tronco nao esta em {TRONCO}. A janela do produto mora la (ADR-0009).\n"
        "Aponte CAISSA_TRONCO para o checkout de ChessVisionOFF_Puro."
    )

# --------------------------------------------------------------------------- #
# datas -- o que o analisador estatico nao enxerga porque e lido por caminho
# --------------------------------------------------------------------------- #
ICONE = TRONCO / "assets" / "cvoff.ico"
"""O icone do `.exe`. Viaja duas vezes de proposito, e a razao e do tronco: cravado no
cabecalho do executavel (o que o Explorer e a barra de tarefas leem antes de o programa
rodar) e dentro de `assets/`, de onde `ui/plataforma.py` o le em execucao."""

PECAS = PACOTE / "assets" / "piece_images"
r"""As 12 pecas vem de `packaging/`, e NAO de `TRONCO/assets/piece_images`.

Isto e uma decisao de licenciamento, e ela esta medida em `packaging/PECAS_PROCEDENCIA.md`:
os 12 PNG do tronco tem IoU **0,9813** de silhueta e RMSE **11,69** de cor (o peao preto:
**0,00**) contra o conjunto `extra/classic` do clone de `tsoj/Chess_diagram_to_FEN`, cujo
`resources/COPYING.md` descreve como *"Chess.com -- All rights reserved. No open-source
license provided."* Nao ha metadado nos arquivos, e o historico do tronco so registra que
eles chegaram prontos no commit inicial.

Os do `packaging/` sao o conjunto **cburnett** (Colin M.L. Burnett, GPLv2+), rasterizado por
`gerar_pecas_livres.py` a partir dos SVG originais, com SHA-256 registrado. Ver
`licenses/PECAS_CBURNETT.md`."""

if not (PECAS / "wk.png").exists():
    raise SystemExit(
        f"Faltam as pecas de licenca conhecida em {PECAS}.\n"
        "Rode `packaging/gerar_pecas_livres.py`. Elas NAO podem ser substituidas pelas do "
        "tronco: ver packaging/PECAS_PROCEDENCIA.md."
    )

LICENCAS = PACOTE / "licenses"
if not (LICENCAS / "INDICE.json").exists():
    raise SystemExit(
        f"Faltam os textos de licenca em {LICENCAS}.\n"
        "Rode `packaging/coletar_licencas.py`. A AGPL-3.0 secao 4 exige que o texto das "
        "licencas acompanhe a distribuicao -- sem esta pasta o pacote nao pode ser entregue "
        "a ninguem, e por isso o build para aqui em vez de sair silenciosamente ilegal."
    )

datas = [
    (str(PECAS), "assets/piece_images"),
    (str(ICONE), "assets"),
    # So `acervo.txt.gz`. Os outros dois lexicos estao no manifesto, nao aqui -- ver o
    # docstring e LICENSING.md.
    (str(TRONCO / "assets" / "lexico" / "acervo.txt.gz"), "assets/lexico"),
    (str(TRONCO / "assets" / "lexico" / "PROCEDENCIA.md"), "assets/lexico"),
    (str(PACOTE / "manifesto.json"), "."),
    (str(PACOTE / "torch_manifesto.json"), "."),
    (str(PROJETO / "LICENSING.md"), "."),
    # A obrigacao da AGPL-3.0 secao 4 e das licencas permissivas, num lugar so.
    (str(LICENCAS), "licenses"),
]

# --------------------------------------------------------------------------- #
# excludes -- conferida contra a medicao, nao contra a memoria
# --------------------------------------------------------------------------- #
excludes = [
    # Ferramenta de desenvolvimento. Cada linha e MB que o usuario baixa e nunca executa.
    "pytest",
    "mypy",
    "mypyc",
    "ruff",
    "IPython",
    "notebook",
    "coverage",
    "PyInstaller",
    "altgraph",
    "pefile",
    "setuptools",
    "pkg_resources",
    "pip",
    "wheel",
    # Segunda opiniao de inferencia, deliberadamente opcional. A ADR-0003 e mais dura que
    # "opcional": onnxruntime-gpu (CUDA 13.0) e torch cu128 no MESMO PROCESSO dao conflito
    # de DLL ou -- pior -- queda silenciosa para CPU. Empacotar os dois lado a lado seria
    # construir o modo de falha que a ADR existe para evitar.
    "onnx",
    "onnxruntime",
    "rapidocr_onnxruntime",
    # 95 MB que entram sem ninguem declarar. Nao sao dependencia deste produto: vem no
    # ambiente por causa do clone de `tsoj/Chess_diagram_to_FEN`, que exige o usuario clonar
    # um repositorio de terceiro e baixar 232 MiB de pesos -- e portanto nao e um caminho do
    # executavel. `tsoj_reader` diz isso em pt-BR quando alguem tenta a opcao no `.exe`.
    "scipy",
    "skimage",
    # Demonstracao, medicao e relatorio. Nada disto e interface.
    "streamlit",
    "altair",
    "pyarrow",
    "matplotlib",
    "tensorboard",
    "pandas",
    # Saiu do tronco com o modo "Leitura" (WebView2). O PyInstaller coleta o que esta
    # INSTALADO e nao o que o pyproject declara, e por isso a linha continua util.
    "pythonnet",
    "clr_loader",
    "clr",
    "webview",
]

if SEM_TORCH:
    # O torch e as bibliotecas que SO ele usa. Sem esta lista o PyInstaller recolheria
    # `sympy` (71,7 MB), `networkx` (15,7 MB) e companhia por causa de um `import` que nao
    # existe mais dentro do bundle -- MB congelados a servico de um pacote que foi embora.
    # As mesmas rodas chegam depois, junto do torch, em `torch_manifesto.json`.
    excludes += [
        "torch",
        "torchvision",
        "torchgen",
        "functorch",
        "sympy",
        "mpmath",
        "networkx",
        "fsspec",
        "filelock",
    ]

_MEDICAO = PACOTE / "modulos_vivos.json"
if _MEDICAO.exists():
    _vivos = set(json.loads(_MEDICAO.read_text(encoding="utf-8"))["vivos"])
    _conflito = sorted(set(excludes) & _vivos)
    if SEM_TORCH:
        # Estes SAO modulos vivos, e sao excluidos assim mesmo -- o que parece violar a regra
        # do tronco e nao viola: a regra diz que um modulo vivo nao pode simplesmente sumir.
        # Aqui ele nao some, ele **muda de lugar**: sai do bundle e entra na primeira
        # execucao, com hash, e o `runtime_hook_torch.py` o poe de volta em `sys.path`. A
        # excecao e nomeada arquivo por arquivo de proposito; qualquer outro nome vivo em
        # `excludes` continua derrubando o build.
        _conflito = [
            n
            for n in _conflito
            if n
            not in {
                "torch",
                "torchvision",
                "torchgen",
                "functorch",
                "sympy",
                "mpmath",
                "networkx",
                "fsspec",
                "filelock",
            }
        ]
    if _conflito:
        raise SystemExit(
            "excludes contem modulo VIVO: " + ", ".join(_conflito) + ".\n"
            f"A regra do tronco (ver docstring) diz que so entra em excludes o que NAO "
            f"aparece em sys.modules depois de importar a arvore. A medicao esta em "
            f"{_MEDICAO}; rode `build_windows.py --medir-modulos` se ela envelheceu."
        )

# --------------------------------------------------------------------------- #
# hiddenimports
# --------------------------------------------------------------------------- #
# Entram por nome porque nada os importa estaticamente. `chess_diagram_ocr` inteiro porque
# `qt/` E a janela: filtra-lo empacotaria um executavel que nao abre. `caissa` inteiro
# porque os subsistemas se resolvem por registro de plugin, nao por import direto.
hiddenimports = [
    "caissa_modelos",
    "caissa_torch",
    "caissa_primeira_execucao",
    "doctor",
    # --- `tkinter` e `PIL.ImageTk`: 12,6 MB que parecem absurdos e nao sao ----------------
    #
    # O sintoma, lido no log do bundle depois de abrir a janela:
    #
    #     WARNING chess_diagram_ocr.ui.icones: Pillow indisponivel: os botoes ficam so com
    #     o texto (S-234).
    #
    # A Pillow **esta** no bundle (12,8 MB de `_internal/PIL/`, com sete `.pyd`). O que nao
    # estava era `_tkinter.pyd`: `ui/icones.py` faz
    # `from PIL import Image, ImageDraw, ImageTk` numa linha so, e `PIL/ImageTk.py` importa
    # `tkinter`, que importa `_tkinter`. Faltando o ultimo, a linha inteira levanta
    # `ImportError`, o `except` do modulo poe `Image = ImageDraw = None`, e o programa perde
    # **todos** os icones da fita por causa de um nome que ele nem usa.
    #
    # Ha um segundo motivo, e ele e o que decide: **`tkinter` esta VIVO** na medicao de
    # `modulos_vivos.json` (o `cli/texto_transcrever.py` do tronco ainda e Tk), e o bundle
    # levava os `.py` de `tkinter` no arquivo compilado **sem** a extensao nativa. Isso e um
    # modulo pela metade -- exatamente a classe de defeito que a regra de `excludes` existe
    # para impedir, so que pelo outro lado.
    #
    # Custo medido: `_tkinter.pyd` 64 KB + `tcl86t.dll` 1,9 MB + `tk86t.dll` 1,5 MB + a
    # pasta `tcl/` 9,1 MB = **12,6 MB**, 1,7% do bundle.
    #
    # O conserto barato nao e aqui: e tirar `ImageTk` daquela linha do tronco, que nao usa
    # Tk desde o corte da S-506. Um `import` morto custando 12,6 MB e o tipo de coisa que so
    # aparece quando alguem empacota. `qt/` e `ui/` do tronco nao sao desta frente; fica
    # registrado no F12_REPORT.md para a F9.
    "tkinter",
    "PIL.ImageTk",
    # --- E a Pillow INTEIRA, pelo mesmo motivo que o `stdlib_do_torch.json` existe --------
    #
    # Enquanto o torchvision estava dentro do bundle, o PyInstaller seguia os imports dele e
    # recolhia `PIL.ImageEnhance`, `PIL.ImageOps` e os outros de tabela. Tirado o torchvision,
    # essa aresta sumiu -- e o defeito voltou pelo outro lado, agora **na janela**, medido no
    # auto-teste do bundle de 2026-09-09:
    #
    #     File "...\runtime\torchvision\transforms\_functional_pil.py", line 7, in <module>
    #         from PIL import Image, ImageEnhance, ImageOps
    #     ImportError: cannot import name 'ImageEnhance' from 'PIL'
    #
    # O torchvision que o assistente instala em `runtime/` importa PIL do `_internal` -- e
    # espera a Pillow completa, nao a fatia que o resto da janela por acaso usa.
    *collect_submodules("PIL"),
]
hiddenimports += collect_submodules("chess_diagram_ocr")
hiddenimports += collect_submodules("caissa")
if COM_TORCH:
    hiddenimports += ["torchvision.models", "torchvision.transforms.v2"]

# --- A BIBLIOTECA PADRAO QUE SO O TORCH USA, e que sem ele ninguem coleta ------------
#
# Tirar o torch do bundle tirou junto uma coisa que ninguem declarou: os modulos da
# **biblioteca padrao** que so ele importa. O PyInstaller coleta o que ve; sem nenhum
# `import torch` na arvore, ele nao ve `uuid`, `unittest.mock`, `asyncio.windows_events`.
#
# O torch instalado depois em `runtime/` acha o proprio pacote e nao acha o Python embaixo
# dele. E o sintoma nao e legivel -- medido com `CaissaPrimeiraExecucao.exe --sondar-torch`:
#
#     -> filelock       FALHOU ModuleNotFoundError: No module named 'uuid'
#     -> torch.version  FALHOU ImportError: cannot import name 'mock' from 'unittest'
#     -> torch._C       EXIT = -1073740791   (0xC0000409, o processo morre sem traceback)
#
# `stdlib_do_torch.json` e a medicao: `build_windows.py --medir-stdlib-do-torch` importa
# torch e torchvision num processo limpo e anota o que entrou em `sys.modules` vindo da
# biblioteca padrao. 178 modulos, identicos nas duas rodas (2.11.0+cu128 e 2.14.0+cpu).
_STDLIB = PACOTE / "stdlib_do_torch.json"
if SEM_TORCH:
    if not _STDLIB.exists():
        raise SystemExit(
            f"{_STDLIB} nao existe.\n"
            "Sem essa medicao o bundle sai sem os modulos da biblioteca padrao que o torch "
            "instalado depois vai procurar, e o `.exe` morre com 0xC0000409 sem traceback. "
            "Rode `build_windows.py --medir-stdlib-do-torch`."
        )
    _stdlib_do_torch = json.loads(_STDLIB.read_text(encoding="utf-8"))["modulos"]
    hiddenimports += _stdlib_do_torch
else:
    _stdlib_do_torch = []

pathex = [
    str(PACOTE),  # caissa_app, caissa_modelos, caissa_primeira_execucao, caissa_setup
    str(PROJETO / "src"),  # caissa
    str(PROJETO / "scripts"),  # doctor
    str(TRONCO),  # app_pyqt
    str(TRONCO / "src"),  # chess_diagram_ocr
]

def binarios_do_torchvision() -> list[tuple[str, str]]:
    r"""Recolhe `torchvision/*.pyd` e `*.dll` a mao, porque o hook do PyInstaller nao os acha.

    **Defeito real, encontrado rodando o `.exe` e nao lendo o codigo.** O auto-teste do bundle
    morria assim:

        File "torchvision\_meta_registrations.py", line 163, in <module>
        RuntimeError: operator torchvision::nms does not exist

    A causa: o `hook-torchvision.py` do PyInstaller 6.22.2 procura `_C.pyd` e `image.pyd`, e o
    torchvision 0.29 renomeou os dois para **`_C_stable.pyd`** e **`image_stable.pyd`**. O hook
    nao acha, **nao reclama**, e coleta zero binario -- o bundle sai com os `.py` do torchvision
    e sem a extensao nativa que registra os operadores. Medido: `_internal/torchvision/` tinha
    14 entradas e **nenhum** `.pyd`; o bundle do tronco, com um torchvision mais antigo, tem
    `_C.pyd` e as seis DLLs.

    Por isso a funcao levanta quando nao encontra nada: o modo de falha original foi uma coleta
    vazia e silenciosa, e repeti-lo com outro nome de arquivo seria trocar um defeito por ele
    mesmo.
    """
    import torchvision

    base = Path(torchvision.__file__).resolve().parent
    achados = sorted(base.glob("*.pyd")) + sorted(base.glob("*.dll"))
    if not achados:
        raise SystemExit(
            f"Nenhum .pyd/.dll em {base}. Sem a extensao nativa, `import torchvision` levanta "
            "`operator torchvision::nms does not exist` -- mas so no `.exe`, e so quando alguem "
            "abre a janela. Confira o layout desta versao de torchvision antes de seguir."
        )
    return [(str(caminho), "torchvision") for caminho in achados]


binaries = binarios_do_torchvision() if COM_TORCH else []

comum = {
    "pathex": pathex,
    "binaries": binaries,
    "hookspath": [],
    "hooksconfig": {},
    # O gancho poe `<pasta do exe>/runtime` em `sys.path` ANTES do script de entrada. Sem
    # ele, o torch instalado ao lado do executavel existiria em disco e nao existiria para
    # o programa -- que e o modo de falha mais confuso possivel para quem acabou de ver uma
    # barra de progresso baixar 2,6 GB.
    "runtime_hooks": [str(PACOTE / "runtime_hook_torch.py")],
    "noarchive": False,
}

# O assistente NAO leva a janela, e a diferenca e medida, nao estimada.
#
# Cada `.exe` carrega o proprio arquivo compilado no cabecalho, e no primeiro build os dois
# levavam a arvore inteira: **44,4 MB + 42,4 MB**, com o segundo pagando de novo por
# `chess_diagram_ocr`, `caissa` e o PyQt6 que ele nunca importa. Ele precisa de tres coisas:
# `doctor` (a sonda real de GPU), `torch` (a referencia de CPU que da a razao medida) e o
# PyMuPDF (o PDF de prova). O resto e peso morto duplicado.
#
# `chess_diagram_ocr` e `caissa` NAO entram em `excludes` aqui -- eles nao sao "modulos que
# nao aparecem em sys.modules", que e o criterio da lista global. Ficam de fora simplesmente
# por nao estarem nos `hiddenimports` deste Analysis, que e a ferramenta certa para "este
# executavel nao usa isto".
excludes_do_assistente = [*excludes, "PyQt6"]
hiddenimports_do_assistente = [
    "caissa_modelos",
    "caissa_torch",
    "caissa_primeira_execucao",
    "doctor",
    "fitz",
    # `torchvision` importa `PIL.ImageDraw` e `PIL.ImageColor`. A Pillow inteira esta em
    # `_internal/` (a janela a coleta), mas cada `.exe` tem o SEU arquivo compilado, e o do
    # assistente so levava `PIL/__init__.py`. Medido pela sonda:
    #     -> torchvision  FALHOU ImportError: cannot import name 'ImageDraw' from 'PIL'
    #
    # A arvore inteira, e nao a lista dos que faltaram: nomear `ImageDraw` fez aparecer
    # `ImageEnhance` no build seguinte, e adivinhar o terceiro seria trocar um defeito por uma
    # rodada de tentativa e erro. A Pillow e ~80 modulos puros; as extensoes nativas ja estao
    # no `_internal` compartilhado, entao o custo aqui e de `.pyc`.
    *collect_submodules("PIL"),
    # O assistente e quem instala o torch e quem roda o `doctor.py` logo depois, no MESMO
    # processo. Se a biblioteca padrao que o torch usa faltar aqui, ele instala 2,6 GB e
    # depois morre ao sondar o que acabou de instalar.
    *_stdlib_do_torch,
]

# --------------------------------------------------------------------------- #
# Dois executaveis, um COLLECT
# --------------------------------------------------------------------------- #
# `Caissa.exe` e uma janela (`console=False`); um assistente que imprime relatorio numa
# janela sem console imprime para lugar nenhum. Por isso o segundo `.exe`, com console.
#
# Os dois saem de Analysis separadas e de um COLLECT so: o segundo carrega apenas o proprio
# arquivo compilado no cabecalho, e as DLLs, o Qt e o Python sao os mesmos de `_internal/`,
# gravados uma vez. O custo esta medido no F12_REPORT.md.
janela = Analysis(  # noqa: F821
    [str(PACOTE / "caissa_app.py")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    **comum,
)
assistente = Analysis(  # noqa: F821
    [str(PACOTE / "caissa_setup.py")],
    datas=[],
    hiddenimports=hiddenimports_do_assistente,
    excludes=excludes_do_assistente,
    **comum,
)

pyz_janela = PYZ(janela.pure)  # noqa: F821
pyz_assistente = PYZ(assistente.pure)  # noqa: F821

exe_janela = EXE(  # noqa: F821
    pyz_janela,
    janela.scripts,
    [],
    exclude_binaries=True,
    name="Caissa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # UPX desligado, e a razao e do tronco e continua valendo: ele comprime as DLLs nativas
    # e uma parte dos antivirus trata binario empacotado por UPX como suspeito. Sem
    # assinatura de codigo, o SmartScreen ja avisa uma vez; trocar MB por um segundo aviso
    # (e por um falso positivo que poe o `.exe` em quarentena) e um mau negocio.
    console=False,
    # Sem console: e um app de janela. O rastro vai para `logs/`, ao lado do executavel --
    # e nao para dentro do bundle, que reinstalar apaga.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICONE),
)

exe_assistente = EXE(  # noqa: F821
    pyz_assistente,
    assistente.scripts,
    [],
    exclude_binaries=True,
    name="CaissaPrimeiraExecucao",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICONE),
)

coll = COLLECT(  # noqa: F821
    exe_janela,
    exe_assistente,
    janela.binaries,
    janela.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=NOME,
)
