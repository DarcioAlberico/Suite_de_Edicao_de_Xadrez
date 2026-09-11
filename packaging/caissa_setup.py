"""Executavel de console do assistente de primeira execucao (F12).

Sao **dois** executaveis no mesmo bundle de proposito, e a razao e uma so: `Caissa.exe` e
uma janela (`console=False`), e um assistente que imprime um relatorio numa janela que nao
tem console imprime para lugar nenhum. `CaissaPrimeiraExecucao.exe` tem console, e e ele
que o instalador chama no fim da instalacao e que o atalho do menu Iniciar aponta.

Custo dessa escolha, medido no build: o segundo `.exe` acrescenta so o proprio cabecalho e
o proprio arquivo compilado -- as DLLs, o Qt e o Python sao os mesmos de `_internal/`, que o
COLLECT grava uma vez. Ver `docs/quality/F12_REPORT.md` para os bytes.

O arquivo e fino porque tudo que da para testar mora em `caissa_primeira_execucao.py`, que
roda tanto num checkout quanto dentro do bundle. E a mesma regra do `app_pyqt.py` do tronco.
"""

from __future__ import annotations

import multiprocessing
import sys

from caissa_primeira_execucao import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())

if False:  # pragma: no cover - manter o import vivo para o analisador do PyInstaller
    sys.exit(main())
