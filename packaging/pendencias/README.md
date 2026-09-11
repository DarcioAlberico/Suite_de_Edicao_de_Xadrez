# `packaging/pendencias/` — o que a F12 não pode consertar sozinha

Esta pasta guarda consertos **escritos, medidos e prontos**, em arquivos do tronco
(`ChessVisionOFF_Puro/`) que a frente F12 não é dona. Cada um traz: o defeito medido, a
medição que o comprova, o patch exato, e o teste desta frente que fica **vermelho** enquanto
o conserto não entra.

Um conserto que existe só na cabeça de quem o descobriu é um conserto perdido no ciclo
seguinte. Um teste vermelho é o único jeito de a lembrança sobreviver a um agente.

| pendência | dono | teste que acusa | estado |
|---|---|---|---|
| `0001-torch-fora-do-escopo-de-modulo.patch` | **F9** (`qt/` e `ui/` do tronco) | `tests/integration/test_packaging.py::TestPendencias::test_a_janela_do_tronco_importa_sem_torch` | **aplicado** — verificado em 2026-09-09 19:0x |

## `0001` — aplicado, e como isso foi verificado

Medido em 2026-09-09 no checkout do tronco, com os quatro arquivos já alterados
(`checkpoint.py`, `inference.py`, `service.py`, `ui/pedido_de_treino.py`):

```
> .venv-pack\Scripts\python.exe  (torch bloqueado por um MetaPathFinder)
  import chess_diagram_ocr.qt.janela                       ->  ok
  controle negativo: import chess_diagram_ocr.dataset      ->  ModuleNotFoundError: 'torch'
  controle negativo: import chess_diagram_ocr.training     ->  ModuleNotFoundError: 'torch'
```

O controle negativo é parte do teste e não um detalhe: sem ele, um bloqueio que não bloqueia
faria a asserção passar sozinha. `dataset` e `training` definem classes que herdam de
`Dataset`/`nn.Module` no escopo de módulo — eles **devem** continuar exigindo torch, e o
patch nunca pretendeu o contrário. O que mudou é que **abrir a janela deixou de importá-los**.

O teste continua no lugar. Se alguém reintroduzir um `import torch` de escopo de módulo em
qualquer ponto da cadeia da janela, ele volta a ficar vermelho.

## Como aplicar

```
cd C:\Python-Chess2\ChessVisionOFF_Puro
git apply --check ..\Suite_de_Edicao_de_Xadrez\packaging\pendencias\0001-torch-fora-do-escopo-de-modulo.patch
git apply           ..\Suite_de_Edicao_de_Xadrez\packaging\pendencias\0001-torch-fora-do-escopo-de-modulo.patch
```

Se o `--check` recusar, os arquivos do tronco mudaram desde 2026-09-09 e o patch precisa ser
reancorado. O patch é um registro do **conteúdo** do conserto, não um artefato imutável: a
seção "As linhas exatas" de cada arquivo descreve a mudança em prosa, e ela continua válida
mesmo que os números de linha andem.
