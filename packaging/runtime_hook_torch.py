r"""Poe `<pasta do executavel>/runtime` em `sys.path` antes de qualquer import (F12, ciclo 2).

Por que um runtime hook, e nao uma linha no `main()`
----------------------------------------------------
O torch nao viaja dentro do instalador (ver `caissa_torch.py`): ele e instalado ao lado do
`.exe`, em `runtime/`, pelo assistente de primeira execucao. Para o programa enxerga-lo, essa
pasta precisa estar em `sys.path` **antes** do primeiro `import torch` -- e o primeiro
`import torch` acontece dentro da arvore do tronco, na cadeia
`qt/janela.py -> qt/campo.py -> field_eval.py -> checkpoint.py`, muito antes de qualquer
codigo desta frente rodar.

Um `runtime_hook` do PyInstaller e exatamente o gancho que roda antes de tudo isso: o
bootloader o executa depois de montar `_internal/` e antes de chamar o script de entrada.
Fazer isso no `main()` do `caissa_app.py` seria tarde para os imports de topo de modulo do
tronco.

Ordem: `append`, e nao `insert(0, ...)`
---------------------------------------
O que esta **dentro** do bundle continua vencendo. O `FrozenImporter` do PyInstaller ja
resolve primeiro os modulos congelados, e acrescentar no fim mantem essa ordem tambem para o
`PathFinder`. `runtime/` so responde pelo que o bundle nao tem -- que e precisamente o torch e
as bibliotecas que so ele usa (`sympy`, `networkx`, `fsspec`, `jinja2`, `filelock`, `mpmath`).

DLLs: o que este gancho NAO faz, e por que
------------------------------------------
Ele **nao** chama `os.add_dll_directory(runtime/torch/lib)`. A primeira versao chamava, com
o argumento de que "um a mais nao custa nada e cobre o caso em que o torch nao o faz". Custa.
Medido no bundle de 2026-09-09, com o torch cu128 (4.230 MB) instalado ao lado:

    > CaissaPrimeiraExecucao.exe --sem-torch --pular-auto-teste
    LASTEXITCODE = -1073740791          (0xC0000409, STATUS_STACK_BUFFER_OVERRUN)

Nenhuma linha impressa: o processo morria **antes** da primeira saida. Renomear
`runtime/torch/lib` fazia o mesmo `.exe` rodar normalmente, com `runtime/` no lugar e o resto
do gancho ativo -- o que isola a causa nesta unica chamada. Nao e colisao de nome: a
intersecao entre os 81 nomes de DLL de `_internal/` (recursivo) e os 37 de `torch/lib` e
**vazia**. O que aquela pasta traz sao 37 DLLs de CUDA e um runtime OpenMP proprio
(`libiomp5md.dll`), e po-las no caminho de busca do processo inteiro, antes de qualquer
`import torch`, muda como TODA carga de DLL do programa se resolve -- inclusive as do Qt e
do OpenCV, que acontecem primeiro.

Quem tem de fazer isso e o proprio `torch/__init__.py`, que chama `os.add_dll_directory` para
o seu `lib` **na hora do import** -- que e quando aquelas DLLs sao de fato necessarias, e
depois de o resto do programa ja ter carregado as suas. E o caminho normal de qualquer venv,
e e o unico testado.

Este arquivo nao levanta. Um hook que quebra impede o programa de abrir -- e a ausencia de
`runtime/` e o estado NORMAL de uma instalacao recem-feita, nao um erro.
"""

# ruff: noqa: PTH100, PTH112, PTH118, PTH120, S110
# `os.path` e nao `pathlib`, e um `except: pass` sem log, os dois de proposito. Este arquivo
# roda no bootloader do PyInstaller, ANTES do script de entrada e antes de qualquer coisa do
# programa existir: nao ha logger configurado para onde escrever, e importar `pathlib` aqui
# poe mais um modulo na frente do primeiro `import torch` sem ganhar nada -- `os` ja esta
# carregado. E um hook que levanta impede o programa de abrir, entao ele nao levanta.
from __future__ import annotations

import os
import sys


def _pasta_do_executavel() -> str:
    """Onde o `.exe` esta. Congelado e a pasta do executavel; fora dela, a raiz do projeto."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _instalar() -> None:
    try:
        runtime = os.path.join(_pasta_do_executavel(), "runtime")
        if not os.path.isdir(runtime):
            return
        if runtime not in sys.path:
            sys.path.append(runtime)
    except Exception:  # noqa: BLE001 - um hook que levanta impede o programa de abrir
        pass


_instalar()
