# Avisos de terceiros - Caissa Studio

Gerado em 2026-09-14 por `packaging/coletar_licencas.py`, a partir dos
metadados das distribuicoes instaladas -- nao de memoria.

O binario do Caissa Studio e uma obra combinada sob **AGPL-3.0-or-later** (ver
`LICENSING.md`). Cada componente abaixo mantem a sua propria licenca; o texto de cada
uma esta nesta pasta, no caminho indicado.

## Textos integrais

| Licenca | Arquivo | bytes | sha256 |
|---|---|---:|---|
| AGPL-3.0 | `AGPL-3.0.txt` | 34520 | `57c8ff33c9c0cfc3...` |
| GPL-3.0 | `GPL-3.0.txt` | 35147 | `8ceb4b9ee5adedde...` |
| LGPL-3.0 | `LGPL-3.0.txt` | 7687 | `6c671e2912ec69c0...` |

## Dependencias distribuidas

| Distribuicao | Versao | Licenca declarada | Onde | Texto |
|---|---|---|---|---|
| chess | 1.11.2 | GPL-3.0+ | `chess` | `chess/LICENSE.txt` |
| filelock | 3.32.3 | MIT | runtime (primeira execucao) | `filelock/LICENSE` |
| fonttools | 4.64.0 | MIT | `fontTools` | `fonttools/LICENSE`, `fonttools/LICENSE.external` |
| fsspec | 2026.7.0 | BSD-3-Clause | runtime (primeira execucao) | `fsspec/LICENSE` |
| Jinja2 | 3.1.6 | BSD License | runtime (primeira execucao) | `Jinja2/LICENSE.txt` |
| MarkupSafe | 3.0.3 | BSD-3-Clause | runtime (primeira execucao) | `MarkupSafe/LICENSE.txt` |
| mpmath | 1.3.0 | BSD | runtime (primeira execucao) | `mpmath/LICENSE` |
| networkx | 3.6.1 | BSD-3-Clause | runtime (primeira execucao) | `networkx/LICENSE.txt` |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | `numpy` | `numpy/COPYING`, `numpy/LICENSE`, `numpy/LICENSE-2`, `numpy/LICENSE-2.md`, `numpy/LICENSE-2.txt`, `numpy/LICENSE-3`, `numpy/LICENSE-3.md`, `numpy/LICENSE-3.txt`, `numpy/LICENSE-4.md`, `numpy/LICENSE-5.md`, `numpy/LICENSE-6.md`, `numpy/LICENSE-7.md`, `numpy/LICENSE-8.md`, `numpy/LICENSE-9.md`, `numpy/LICENSE.md`, `numpy/LICENSE.txt`, `numpy/dragon4_LICENSE.txt` |
| opencv-python-headless | 4.14.0.94 | Apache 2.0 | `cv2` | `opencv-python-headless/LICENSE-3RD-PARTY.txt`, `opencv-python-headless/LICENSE.txt` |
| pillow | 12.3.0 | MIT-CMU | `PIL` | `pillow/LICENSE` |
| platformdirs | 4.11.8 | MIT | `platformdirs` | `platformdirs/LICENSE` |
| pyinstaller | 6.22.2 | GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones) | `PyInstaller` | `pyinstaller/COPYING.txt` |
| pymupdf | 1.28.2 | Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License | `fitz`, `pymupdf` | `pymupdf/COPYING` |
| PyQt6 | 6.11.0 | GPL-3.0-only | `PyQt6` | `PyQt6/LICENSE` |
| PyQt6-Qt6 | 6.11.2 | LGPL v3 | bundle | `PyQt6-Qt6/LICENSE` |
| PyQt6_sip | 13.12.0 | BSD-2-Clause | `PyQt6` | `PyQt6_sip/LICENSE` |
| sympy | 1.14.0 | BSD | runtime (primeira execucao) | `sympy/AUTHORS`, `sympy/LICENSE` |
| torch | 2.14.0+cpu (cpu) ou 2.11.0+cu128 (cu128) | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT | runtime (primeira execucao) | `torch/LICENSE`, `torch/LICENSE-10`, `torch/LICENSE-10.txt`, `torch/LICENSE-11`, `torch/LICENSE-11.txt`, `torch/LICENSE-12`, `torch/LICENSE-12.txt`, `torch/LICENSE-13`, `torch/LICENSE-14`, `torch/LICENSE-15`, `torch/LICENSE-16`, `torch/LICENSE-17`, `torch/LICENSE-18`, `torch/LICENSE-19`, `torch/LICENSE-2`, `torch/LICENSE-2.rst`, `torch/LICENSE-2.txt`, `torch/LICENSE-20`, `torch/LICENSE-21`, `torch/LICENSE-22`, `torch/LICENSE-23`, `torch/LICENSE-24`, `torch/LICENSE-25`, `torch/LICENSE-26`, `torch/LICENSE-27`, `torch/LICENSE-28`, `torch/LICENSE-29`, `torch/LICENSE-3`, `torch/LICENSE-3.rst`, `torch/LICENSE-3.txt`, `torch/LICENSE-30`, `torch/LICENSE-31`, `torch/LICENSE-32`, `torch/LICENSE-33`, `torch/LICENSE-34`, `torch/LICENSE-35`, `torch/LICENSE-36`, `torch/LICENSE-37`, `torch/LICENSE-38`, `torch/LICENSE-4`, `torch/LICENSE-4.txt`, `torch/LICENSE-5`, `torch/LICENSE-5.txt`, `torch/LICENSE-6`, `torch/LICENSE-6.txt`, `torch/LICENSE-7`, `torch/LICENSE-7.txt`, `torch/LICENSE-8`, `torch/LICENSE-8.txt`, `torch/LICENSE-9`, `torch/LICENSE-9.txt`, `torch/LICENSE.rst`, `torch/LICENSE.txt` |
| torchvision | 0.29.0+cpu (cpu) ou 0.26.0+cu128 (cu128) | BSD | runtime (primeira execucao) | `torchvision/LICENSE` |
| typing_extensions | 4.16.0 | PSF-2.0 | `typing_extensions` | `typing_extensions/LICENSE` |

## Artefatos que nao sao distribuicoes Python

| Artefato | Licenca | Registro |
|---|---|---|
| assets/piece_images/ (12 PNG de peca, conjunto cburnett) | GPL-2.0-or-later, redistribuido sob GPL-3.0 (Colin M.L. Burnett) | `PECAS_CBURNETT.md` |
| assets/piece_images/ do tronco - NAO DISTRIBUIDO | NAO APURADA - a arte foi medida como identica a um conjunto descrito como 'All rights reserved' | `PECAS_PROCEDENCIA.md` |
| assets/lexico/acervo.txt.gz | do projeto (derivado do acervo do dono do projeto) | - |

## O que a AGPL-3.0 exige de quem distribui este build

1. Entregar o **codigo-fonte correspondente** -- o do Caissa e o das bibliotecas
   copyleft -- ou uma oferta escrita e valida de obte-lo, junto com o binario.
2. Manter os avisos de copyright e **entregar o texto das licencas** (esta pasta).
3. Licenciar o conjunto sob **AGPL-3.0-or-later**, e nao sob termos mais restritivos.
4. Nao impedir que o usuario modifique e reinstale.
5. Secao 13: se o programa **modificado** for oferecido pela rede, o fonte vai para os
   usuarios desse servico, mesmo sem distribuir binario nenhum.

