# F12 — Empacotamento e distribuição: o que foi construído e o que foi medido

> **Data:** 2026-09-09 · **Máquina:** a de referência da SPEC §2 (Ryzen 5 8400F, 31,6 GiB,
> RTX 5060 8 GB `sm_120`, Windows 11 Pro 26200, C: 930 GB).
>
> **Regra deste relatório:** todo número veio de um comando executado nesta máquina em
> 2026-09-09. Onde não houve medição, está escrito que não houve — a seção 8 lista o que
> **não** foi verificado, e é a seção mais importante para quem for continuar.

---

## 0. Conclusão em uma tela

| Pergunta | Resposta medida |
|---|---|
| O bundle existe? | **Sim.** `dist/Caissa/`, `--onedir`, dois executáveis. |
| Ele abre? | **Sim.** Ver §5 — auto-teste do tronco e captura da janela aberta com um livro. |
| Tamanho do bundle | **730,6 MB em 3.892 arquivos** — variante leve: **293,9 MB / 1.204** (tronco: 684,2 MB / 4.276) |
| Tamanho do instalador | **169,3 MB** completo · **79,1 MB** leve (proxy LZMA2 medido; o Inno Setup **não** está nesta máquina) |
| Teto da SPEC §12 | 150 MB — a **leve cabe** (79,1); a **completa não** (169,3, +19,3). §3 mede a diferença: é o torch. |
| Pesos dentro do bundle? | **Nenhum.** 0 `.pt`, 0 `.onnx`, 0 `.safetensors`, 0 `.gguf`. |
| LLM empacotado? | **Não**, e não está nem no manifesto. F11 mediu especificidade 0,000. |
| Licença do binário | **AGPL-3.0** — não só GPL. Ver `LICENSING.md` §1. |
| Disco antes / depois | **48,67 GB → 45,43 GB livres** (−3,24 GB) |

---

## 1. O que foi entregue

```
packaging/
  caissa.spec                 a spec do PyInstaller, duas variantes por CAISSA_LIGHT
  build_windows.py            o driver: confere disco, monta, mede, comprime
  installer.iss               o Inno Setup, adaptado do Editor_Diagramas_de_Xadrez
  caissa_app.py               ponto de entrada da janela (casca fina sobre app_pyqt.py)
  caissa_setup.py             ponto de entrada do assistente (console)
  caissa_primeira_execucao.py o assistente: GPU, componentes, auto-teste
  caissa_modelos.py           manifesto, SHA-256, instalação offline, download
  manifesto.json              5 componentes, hash e tamanho medidos em disco
  modulos_vivos.json          a medição que torna a regra de `excludes` executável
  bundle.json                 as métricas deste build
LICENSING.md                  a consequência da ADR-0009, e a que ela não previa
tests/integration/test_packaging.py   52 testes
```

Origem, conforme `docs/ASSETS.md` §5 e §6: `caissa.spec` e `build_windows.py` vêm de
`ChessVisionOFF_Puro/packaging/`; `installer.iss` vem de
`Editor_Diagramas_de_Xadrez/packaging/`; `test_packaging.py` vem de
`ChessVisionOFF_Puro/tests/`. Cada arquivo declara a origem e o que mudou no cabeçalho.

### O que o bundle é

A janela do produto **é a do tronco** (`ChessVisionOFF_Puro/app_pyqt.py`), pela ADR-0009.
Isso não foi uma escolha desta frente e sim uma constatação: `src/caissa/ui/` tem
`views/`, `widgets/`, `theme/` e `resources/` **vazios** — só `audit/` está povoado, e é
código de teste que dirige a janela do tronco. Não existe janela própria da suíte para
empacotar. O que a suíte acrescenta (`src/caissa/`: Document IR, notação, tipografia,
exportadores, índice, OCR, visão) viaja no mesmo arquivo compilado e fica importável de
dentro da janela.

Ambiente de empacotamento: **`.venv-pack`** (CPython 3.11.9), criado para esta frente. O
`.venv` principal **não foi tocado** — instalar PyQt6 nele mudaria quais testes da suíte
são pulados, e o portão diz 3022 passados / 1 pulado.

---

## 2. Tamanho: os números, e de onde saíram

### 2.1 O bundle

| dentro do bundle | MB | % |
|---|---:|---:|
| `torch` | 365,1 | 50,0% |
| `cv2` | 100,4 | 13,7% |
| `PyQt6` | 72,1 | 9,9% |
| `pymupdf` | 37,7 | 5,2% |
| `numpy.libs` | 20,0 | 2,7% |
| `PIL` | 12,8 | 1,8% |
| `numpy` | 5,9 | 0,8% |
| `python311.dll` | 5,5 | 0,8% |
| `libcrypto-3.dll` | 5,0 | 0,7% |
| `torchvision` | 4,1 | 0,6% |
| `_tcl_data` | 3,2 | 0,4% |
| `torch-2.14.0+cpu.dist-info` | 1,7 | 0,2% |
| **total** | **730,6** | **3.892 arquivos** |

### 2.2 A comparação com o tronco, e uma ressalva que muda a leitura

O tronco declara 684 MB em `docs/metrics/bundle.json`. Medido em disco em 2026-09-09,
`ChessVisionOFF_Puro/dist/ChessVisionOFF/` tem **684,2 MB em 4.276 arquivos** — o número
publicado confere.

**Mas o conteúdo não é o que a `cvoff.spec` de hoje produziria.** Medindo o `_internal/`
daquele build:

| dentro do bundle do tronco | MB | a `cvoff.spec` declara |
|---|---:|---|
| `scipy` | 62,5 | `"scipy"` em `excludes` |
| `scipy.libs` | 19,2 | (não coberto por `"scipy"`) |
| `pandas` | 16,6 | não está em `excludes` |
| `skimage` | 11,3 | `"skimage"` em `excludes` |
| **soma** | **109,6** | |

O bundle no disco é de **2026-08-18** (commit `9a683d1`) e carrega 109,6 MB de bibliotecas
que a spec atual exclui — ou ele é anterior à exclusão, ou a exclusão não pegou. De
qualquer forma: **684 MB não é o número que um rebuild do tronco daria hoje**, e comparar
contra ele sem esta ressalva seria comparar contra um alvo que não existe.

E há uma segunda assimetria, maior: **aquele bundle não tem PyQt6.** Ele é anterior ao
corte do Tk (S-506), e sua janela era Tk. O nosso carrega 72,1 MB de Qt — que é a janela.

| | tronco (2026-08-18) | Caïssa (2026-09-09) |
|---|---:|---:|
| torch | 314,9 | 365,1 |
| cv2 | 98,6 | 100,4 |
| **PyQt6 (a janela)** | **0** | **72,1** |
| pymupdf | 36,4 | 37,7 |
| scipy + libs + pandas + skimage | **109,6** | **0** |
| executáveis | 34,8 (um) | **82,9 (dois)** |

**Leitura honesta: não batemos os 684 MB — ficamos em 730,6 MB.** O que trocamos foi
109,6 MB de bibliotecas de desenvolvimento que o tronco carrega sem declarar, por 72,1 MB
de toolkit de interface (a janela, que aquele build não tinha) e 40,5 MB de um segundo
executável. Descontando o Qt, que é funcionalidade e não gordura, o bundle está **abaixo**
do tronco; contando tudo, está 46,4 MB acima, e a §2.3 mostra onde.

### 2.3 Os dois executáveis: 1,9 MB de programa, 40,5 MB de torch duplicado

Medido nos dois `.exe` do build final:

| | bytes | MB | o que carrega no cabeçalho |
|---|---:|---:|---|
| `Caissa.exe` | 44.440.612 | 42,38 | torch + `chess_diagram_ocr` + `caissa` + PyQt6 |
| `CaissaPrimeiraExecucao.exe` | 42.446.865 | 40,48 | torch + `doctor` + PyMuPDF |
| **diferença** | **1.993.747** | **1,90** | **todo o código da aplicação** |

Ou seja: o programa inteiro — as ~19.600 linhas de interface do tronco, o `caissa` da suíte
e as ligações do PyQt6 — cabe em **1,9 MB**. Os outros 40,5 MB de cada executável são a
árvore `.pyc` do torch, **paga duas vezes**.

**O experimento que provou isso, e que falhou como economia.** No primeiro build os dois
`Analysis` levavam a árvore inteira. Estreitei o do assistente — fora `chess_diagram_ocr`,
fora `caissa`, fora PyQt6 — e remedi os dois `.exe` do build seguinte:

```
antes (dois PYZ completos):  Caissa.exe 44.352.255   Assistente 42.445.434
depois (assistente enxuto):  Caissa.exe 44.352.463   Assistente 42.445.642
delta                     :         +208 bytes             +208 bytes
```

**Os mesmos 208 bytes nos dois** — ruído de build, e economia zero. A exclusão *funcionou*:
busca binária nos arquivos mostra `chess_diagram_ocr.qt.janela` presente 1 vez em
`Caissa.exe` e **0 vezes** no assistente, com `torch.nn.modules` aparecendo **28 vezes nos
dois**. Ela simplesmente não importa, porque o que pesa é o torch.

**A conclusão que isso obriga:** o custo do desenho de dois executáveis é 40,5 MB, e a única
forma de eliminá-lo é um executável só com despacho por modo — ao preço de um assistente de
console que não tem console (um `.exe` com `console=False` não imprime relatório nenhum).
Como a §3 mostra que nem isso chegaria perto do teto de 150 MB, os dois executáveis ficam.

### 2.4 torch: cu128 contra CPU

| roda | tamanho instalado | onde foi medido |
|---|---:|---|
| `torch` cu128 (Blackwell) | **4.214,4 MB** | `.venv` principal da suíte |
| `torch` 2.14.0+cpu | **506,1 MB** | `.venv-pack` |

**8,3× de diferença.** Nenhum instalador carrega as rodas CUDA; nem sob AGPL, nem sob
qualquer outra licença. O bundle leva o torch de CPU, e quem tem a RTX instala o cu128 ao
lado — o assistente mede a diferença e diz o número (§4).

---

## 3. O teto de 150 MB da SPEC §12: medido nas duas variantes

**As duas foram construídas e as duas foram medidas.**

| | bundle | arquivos | instalador (proxy LZMA2) | teto de 150 MB |
|---|---:|---:|---:|---|
| **completo** (com torch CPU) | 730,6 MB | 3.892 | **169,3 MB** | **19,3 MB acima** |
| **leve** (sem torch) | 293,9 MB | 1.204 | **79,1 MB** | **70,9 MB de folga** |
| diferença | **436,7 MB** | 2.688 | **90,2 MB** | |

**O torch custa 436,7 MB de bundle e 90,2 MB de instalador.** Ele sozinho decide se a SPEC
§12 é cumprida: sem ele o teto é atingido com quase metade de folga; com ele não há
compressão que resolva.

### Por que a variante leve, que cabe, não é distribuível

Porque ela não abre. Medido, rodando o `.exe` da variante leve:

```
> dist\Caissa-leve\Caissa.exe --selftest --pdf PDF\prova.pdf
ModuleNotFoundError: No module named 'torch'
  File "chess_diagram_ocr\service.py", line 46, in <module>
  File "chess_diagram_ocr\dataset.py", line 12, in <module>
CODIGO DE SAIDA = 7
```

`chess_diagram_ocr/qt/janela.py` importa `torch` no topo do módulo — medido: dos 50 módulos
que falham num ambiente sem torch, **7 são de `qt/`, inclusive a janela**. A variante leve
não é um produto com menos funções: é um produto que não inicia.

*(Repare, de passagem, que ela morre em segundos com o traceback no log e o código 7, e não
travada numa caixa modal por 7 minutos. É o conserto da §5.3(b) funcionando.)*

### O que custaria cumprir o teto

O caminho é conhecido e **não é desta frente** — a regra diz que `qt/` e `ui/` do tronco não
são meus:

1. `qt/janela.py` e os outros 6 módulos de `qt/` passam a importar torch **dentro** das
   funções que o usam. O padrão a copiar já existe e é da própria suíte:
   `src/caissa/vision/runtime/device.py` faz exatamente isso, com estado de erro e
   degradação — e é por isso que `caissa` inteiro importa num ambiente sem torch e o tronco
   não.
2. O bundle padrão passa a ser o leve (**79,1 MB de instalador, medidos**), e o torch vira
   componente de primeira execução, ao lado dos pesos.
3. O caminho neural fica indisponível até o usuário instalá-lo, e o assistente diz isso —
   que é o mesmo contrato que ele já aplica aos pesos e aos léxicos.

Enquanto isso não acontece, **o teto de 150 MB é uma meta descumprida por 19,3 MB, com causa
identificada, custo medido e conserto escrito** — e não uma medição que ninguém fez.

---

## 4. O que foi excluído, e por quê

### 4.1 A regra de `excludes`, agora executável

O tronco escreveu a regra certa: *"só entra em `excludes` o que NÃO aparece em `sys.modules`
depois de importar o pacote"*. Ela era um comentário — e um comentário não impede ninguém de
excluir um módulo vivo e descobrir na máquina do usuário.

`build_windows.py --medir-modulos` importa a árvore inteira num processo limpo e grava
`packaging/modulos_vivos.json`. A `caissa.spec` lê esse arquivo e **recusa montar o bundle**
se algum nome de `excludes` estiver na lista de vivos. `test_packaging.py` reconfere.

Medição de 2026-09-09: **152 módulos de primeiro nível vivos, 0 falhas de import**.

**A regra tem dois lados, e o segundo custou um defeito para aparecer.** `tkinter` está
vivo (o `cli/texto_transcrever.py` do tronco ainda é Tk), e por isso não está em
`excludes` — igual ao tronco. Mas *não excluir* não bastou: o PyInstaller levou os `.py` de
`tkinter` e deixou `_tkinter.pyd` de fora, e um módulo pela metade quebra tão bem quanto um
ausente (§5.3c). Um módulo vivo tem de ser **pedido**, com a extensão nativa junto — que é
o que `hiddenimports` faz e o que `test_o_tkinter_esta_vivo_e_por_isso_e_pedido_em_vez_de_excluido`
agora afirma.

### 4.2 Fora do bundle — a lista, com o motivo de cada linha

| o que | por quê |
|---|---|
| `scipy`, `skimage` | vêm do clone de `tsoj/Chess_diagram_to_FEN`, que não é caminho do executável. No tronco isso custou 93 MB não declarados. |
| `onnx`, `onnxruntime`, `rapidocr_onnxruntime` | **ADR-0003.** Não é "opcional": onnxruntime-gpu (CUDA 13.0) e torch cu128 no mesmo processo dão conflito de DLL ou queda silenciosa para CPU. Empacotar os dois seria construir o modo de falha que a ADR existe para evitar. |
| `pandas`, `pyarrow`, `matplotlib`, `streamlit`, `altair`, `tensorboard` | medição, relatório e demonstração. Nada disso é interface. |
| `pytest`, `mypy`, `ruff`, `coverage`, `PyInstaller`, `setuptools`, `pip` | ferramenta de desenvolvimento. |
| `pythonnet`, `clr_loader`, `webview` | saíram do tronco com o modo "Leitura"; o PyInstaller coleta o que está **instalado**, não o que o `pyproject` declara. |
| **os pesos** (`models/*.pt`, 11,5 MB) | SPEC §12, e um segundo motivo do tronco: modelo dentro do `.exe` é o único que o usuário não consegue trocar depois de retreinar. |
| **`idioma.txt.gz` e `nomes.txt.gz`** (1,12 MB) | **licença, não tamanho.** §6. |
| **o LLM** | F11 mediu Gemma 4 E4B com **especificidade 0,000** na verificação de diagramas — ele aprova tudo, inclusive os 50 pares deliberadamente errados. Gigabytes de pesos para um veredito que não discrimina. Não é empacotado, não é baixado, e **não está no manifesto**. |

### 4.3 Um defeito de dependência encontrado no caminho

O `.venv-pack` tinha `opencv-python-headless` **5.0.0.93**, e o `pyproject.toml` da suíte
declara `>=4.10,<5`. O ambiente violava a própria restrição do projeto. Corrigido para
**4.14.0.94** antes do build final. (Medido: não muda o tamanho — as duas rodas têm ~110 MB.
O ganho aqui é de correção, não de bytes.)

---

## 5. A prova de que abre

Três provas, em ordem crescente de exigência. Todas contra `dist/Caissa/`, nenhuma contra o
checkout.

### 5.1 O assistente de primeira execução, rodado do bundle

```
> dist\Caissa\CaissaPrimeiraExecucao.exe --de-pasta C:\Python-Chess2\ChessVisionOFF_Puro

==========================================================================
  Caissa Studio - primeira execucao
  pasta: C:\Python-Chess2\Suite_de_Edicao_de_Xadrez\dist\Caissa
==========================================================================

[INFO ] Maquina
         AMD Ryzen 5 8400F 6-Core Processor - 6C/12T - 31.6 GiB, 16.2 GiB livres

[AVISO] GPU
         nao utilizavel - caminho de CPU
         O programa RODA NA CPU. Nada quebra: a deteccao geometrica, o OCR, a notacao,
         a tipografia e os exportadores nao usam GPU. O que fica lento e o caminho
         neural, na ordem de 54x.

[ OK  ] Classificador de casas (pecas)
         instalado (8.4 MB)  de ...\ChessVisionOFF_Puro\models\piece_classifier.pt
[ OK  ] Classificador de caracteres (OCR por glifo)
         instalado (2.7 MB)  de ...\ChessVisionOFF_Puro\models\char_classifier.pt
[ OK  ] Metadados do classificador de caracteres
         instalado (0.0 MB)  de ...\ChessVisionOFF_Puro\models\char_meta.json

[INFO ] Lexico de idioma (10.010 palavras)
         sem-consentimento
         NAO ENTRA POR DECISAO DE LICENCA, e nao por falta de espaco.
         Licenca: NAO APURADA.
         [...] sai de 'Dic-1.txt' e 'Novo Documento de Texto.txt', que chegaram sem
         cabecalho, licenca nem README. Origem nao declarada.
         Sem ele: [...] nenhum caractere muda no texto entregue; 39 palavras deixam de
         ser protegidas contra reescrita do dicionario.
         Para instalar assim mesmo: --de-pasta <origem> --aceitar-licenca-nao-apurada

[INFO ] Lexico de nomes de jogadores (349.565 nomes)
         sem-consentimento
         [...] 0,4% vem exclusivamente de 'MegaDatabase(Jogadores).txt' -- um extrato
         do indice de jogadores da base COMERCIAL da ChessBase [...]

[ OK  ] Auto-teste
         codigo 0 - a instalacao le um diagrama (4.5 s)
         INFO app_pyqt:   diagrama 1: 4k2r/8/8/3p4/3P4/8/8/R3K3 | conf min 0.804 | legal
         INFO app_pyqt: Auto-teste concluido: 1 diagrama(s) reconhecido(s).
         INFO app_pyqt: Auto-teste: o caminho de treino tambem montou (leitor + treinador).
         INFO app_pyqt: Auto-teste: classificador de caracteres -- presente em [...]\models.
         INFO app_pyqt: as 3 peles registradas montam o cromo.

[INFO ] Disco
         46.1 GB livres - instalacao ocupa 734 MB

--------------------------------------------------------------------------
Funciona, com menos. Cada AVISO acima diz o que falta e o que se perde.
--------------------------------------------------------------------------
EXIT=3
```

**Lendo a transcrição:**

- **`codigo 0` no auto-teste é a prova central.** O `--selftest` é o do tronco, chamado
  como `Caissa.exe --selftest` a partir do bundle, sobre um PDF que o assistente **desenhou
  na hora** com o PyMuPDF do bundle e os PNGs de peça do bundle. Ele leu
  `4k2r/8/8/3p4/3P4/8/8/R3K3` — exatamente a posição desenhada (reis em e1/e8, torres em
  a1/h8, peões em d4/d5) — com confiança mínima 0,804 e veredito **legal**. É o caminho
  inteiro: PDF → detecção → retificação → classificação → decodificação com restrições →
  FEN. **4,5 segundos, em CPU.**
- **A GPU aparece como AVISO e não como falha**, e a frase diz o que se perde e o que não.
  O bundle leva torch de CPU: é isso que `nao utilizavel` significa aqui, e o número `54x`
  foi medido **nesta execução**, não copiado.
- **Saída 3 e não 1.** Três é "funciona, com menos". Devolver 1 diria que a instalação está
  quebrada — e ela não está.
- **Os dois léxicos aparecem como INFO com a licença escrita**, sem terem sido instalados,
  mesmo com `--de-pasta` apontando para uma pasta que os contém. Foi preciso um conserto
  para chegar nisso: a primeira versão só imprimia a razão de licença quando o usuário já
  tinha pedido a instalação offline; quem não pedisse via um `ausente` seco. O motivo de um
  componente faltar é exatamente a informação que o assistente existe para dar.

Rodando com GPU (fora do bundle, no `.venv` principal, que tem torch cu128):

```
[ OK  ] GPU
         cuda:0 - 5.4 ms (25.4 TFLOP/s)
         Kernel real de 4096x4096 em float16, nao `is_available()` (ADR-0003).
         Medido agora: a GPU e 72x a CPU desta maquina.
```

A sonda é a do `scripts/doctor.py`, reusada e não reescrita: multiplicação real de
4096×4096 conferida contra referência de CPU, porque em `sm_120` o modo de falha é
silencioso (ADR-0003).

### 5.2 A janela, aberta, com um livro de verdade

![A janela do Caïssa Studio rodando a partir de `dist/Caissa/`, com um livro de 308 páginas aberto](F12_janela_do_bundle.png)

`dist\Caissa\Caissa.exe --pdf "PDF\Xadrez Vitorioso - Finais - Yasser Seirawan.pdf"`.
Título da janela lido do sistema:
`Xadrez Vitori…Finais - Yasser Seirawan.pdf · p. 1 de 308 — ChessVisionOFF — PyQt`.

A captura é do **buffer da própria janela** (`PrintWindow`), e não da tela: uma primeira
tentativa com `CopyFromScreen` pegou a janela que o usuário tinha em primeiro plano, e foi
descartada. Um relatório que ilustra "o programa abre" com a tela de outra pessoa não prova
nada.

### 5.3 Os três defeitos que só apareceram porque o `.exe` foi rodado

Nenhum destes é encontrável lendo código. Todos os três passariam por qualquer revisão e
apareceriam na máquina do usuário.

#### (a) `RuntimeError: operator torchvision::nms does not exist`

O auto-teste do primeiro bundle morria assim, no `import torchvision`. Causa medida: o
`hook-torchvision.py` do PyInstaller 6.22.2 procura `_C.pyd` e `image.pyd`; o torchvision
0.29 renomeou os dois para **`_C_stable.pyd`** e **`image_stable.pyd`**. O hook não
encontra, **não reclama**, e coleta zero binário — o bundle saiu com os `.py` do torchvision
e sem a extensão nativa que registra os operadores. Medido: `_internal/torchvision/` tinha
14 entradas e **nenhum `.pyd`**; o bundle do tronco, com um torchvision mais antigo, tem
`_C.pyd` e as seis DLLs, e por isso o tronco nunca viu isto.

Conserto: `binarios_do_torchvision()` na spec recolhe `*.pyd` e `*.dll` à mão e **derruba o
build** se não achar nada — porque o defeito original foi uma coleta vazia e silenciosa, e
repeti-la com outro nome de arquivo seria trocar um bug por ele mesmo. Guarda:
`test_o_torchvision_levou_a_extensao_nativa`.

#### (b) A caixa modal que travou o auto-teste por 7 min 10 s

O erro acima não apareceu como erro: apareceu como **tempo esgotado**. `Caissa.exe` é
`console=False`, e quando uma exceção escapa de um `.exe` sem console o PyInstaller abre uma
**caixa de diálogo modal** com o traceback e espera alguém clicar. O assistente, chamado
sem ninguém olhando (que é exatamente como o instalador o chama), ficou **7 minutos e 10
segundos** parado nela, e o relatório disse *"não terminou"* — a coisa menos útil possível
sobre um `RuntimeError` perfeitamente diagnóstico.

Conserto: `caissa_app.main()` captura tudo, grava o traceback inteiro em `logs/` ao lado do
executável e devolve **código 7** (distinto dos 1–6 do `--selftest` do tronco, cada um com
sua causa). O erro não some; some a caixa que trava a máquina de quem instalou. Guarda:
`TestJanelaNaoTrava`.

#### (c) Todos os ícones da fita sumiram, e a culpa era de um `import` morto

Lido no log da primeira janela que abriu:

```
WARNING chess_diagram_ocr.ui.icones: Pillow indisponivel: os botoes ficam so com o
texto (S-234).
```

A Pillow **estava** no bundle: 12,8 MB de `_internal/PIL/`, com sete `.pyd`. O que faltava
era `_tkinter.pyd`. `ui/icones.py` faz `from PIL import Image, ImageDraw, ImageTk` numa
linha só; `PIL/ImageTk.py` importa `tkinter`, que importa `_tkinter`. Faltando o último, a
linha inteira levanta, o `except` do módulo põe `Image = ImageDraw = None`, e o programa
perde **todos** os ícones por causa de um nome que não usa desde o corte do Tk (S-506).

Havia um segundo sintoma no mesmo defeito, e é ele que decidiu o conserto: **`tkinter` está
vivo** em `modulos_vivos.json` (o `cli/texto_transcrever.py` do tronco ainda é Tk), e o
bundle levava os `.py` de `tkinter` **sem** a extensão nativa. Isso é um módulo pela metade
— a mesma classe de defeito que a regra de `excludes` existe para impedir, pelo outro lado.

Conserto: `tkinter` e `PIL.ImageTk` em `hiddenimports`. Custo medido: `_tkinter.pyd` 64 KB +
`tcl86t.dll` 1,9 MB + `tk86t.dll` 1,5 MB + dados do Tcl/Tk 9,1 MB = **12,6 MB, 1,7% do
bundle**. Guarda: `test_o_tkinter_levou_a_extensao_nativa`.

**O conserto barato não é este, e não é meu.** É apagar `ImageTk` daquela linha do tronco,
que não usa Tk há um corte inteiro — e aí os 12,6 MB saem junto. `ui/` e `qt/` do tronco não
são desta frente; fica registrado para a F9.

Depois do conserto, o log da janela sai limpo, sem nenhum aviso de degradação, e os ícones
aparecem na captura da §5.2.

---

## 6. Licenciamento — o resumo; o detalhe está em `LICENSING.md`

Medido em 2026-09-09 por `importlib.metadata` no `.venv-pack`, não de memória:

| componente | versão | licença declarada |
|---|---|---|
| **PyMuPDF** | 1.28.2 | `Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License` |
| **PyQt6** | 6.11.0 | `License-Expression: GPL-3.0-only` |
| python-chess | 1.11.2 | `GPL-3.0+` |
| PyInstaller | 6.22.2 | GPLv2+ **com exceção de bootloader** (não contamina o app congelado) |
| torch, numpy, Pillow, OpenCV, fontTools | — | Apache-2.0 / BSD / MIT / MIT-CMU |

**Três consequências, em ordem de importância:**

1. **O binário é AGPL-3.0, não GPL.** A ADR-0009 registrou honestamente que PyQt6 é GPL e
   que distribuir binário fechado exigiria licença da Riverbank ou migração para PySide6. A
   medição confirma a ADR **e acrescenta uma dependência mais forte que ela não citava**: o
   PyMuPDF é AGPL, e a AGPL §13 alcança uso em rede. Para um app de desktop instalado isso
   não muda nada hoje; muda no dia em que alguém puser o Caïssa atrás de um serviço.

2. **`pyproject.toml` declara `LGPL-3.0-or-later`, e isso não pode estar certo.** Com
   PyMuPDF, PyQt6 e python-chess no conjunto, um binário distribuído não pode ser LGPL. É
   uma linha de `pyproject.toml`, que não é arquivo desta frente — registrado para quem for.

3. **Os dois léxicos de licença não apurada não estão no bundle.** O
   `PROCEDENCIA.md` do tronco registra que `idioma.txt.gz` vem de arquivos *"sem cabeçalho,
   licença nem README"* e que parte de `nomes.txt.gz` é um extrato do índice de jogadores da
   MegaDatabase da **ChessBase — base comercial** —, e fecha com *"Decisão: pendente do dono
   do projeto"*. Uma decisão pendente não é uma autorização, e distribuir é o ato que cria a
   responsabilidade. Eles estão em `manifesto.json` com `"consentimento": true` e só entram
   com `--aceitar-licenca-nao-apurada`. **O custo está medido pelo próprio tronco: nenhum
   caractere muda** no texto entregue em 40 páginas de 11 livros; perdem-se 39 + 22 palavras
   de proteção contra reescrita do dicionário.

**A lacuna assumida:** `assets/piece_images/` (12 PNG, 40 KB) entra no bundle **sem arquivo
de procedência**. O código do tronco os chama de "os PNGs do próprio tronco", mas nenhum
arquivo diz quem os desenhou. O dono do projeto precisa confirmar a autoria antes de um
release público. Está escrito em `LICENSING.md` §2.1 que é hipótese, não fato.

**E outra, que impede a entrega hoje:** faltam os textos completos da AGPL-3.0, GPL-3.0 e
LGPL-3.0 e o arquivo consolidado de avisos de terceiros dentro do pacote. A AGPL exige que
acompanhem a distribuição. Até isso ser feito, **o build é para uso próprio.**

---

## 7. Os testes

`tests/integration/test_packaging.py` — 52 testes, adaptados de
`ChessVisionOFF_Puro/tests/test_packaging.py`. Divididos entre os que sempre rodam (a spec,
o manifesto, o `.iss` e a verificação SHA-256 são arquivos e funções) e os que **pulam com
o motivo** se não houver build — porque um teste verde que nunca viu um bundle não diz nada
sobre o bundle.

O que o pedido desta frente exigia, e onde está:

| exigência | teste |
|---|---|
| nenhum módulo só como `.pyc` que o PyInstaller perdeu | `test_nenhum_modulo_ficou_so_como_pyc_solto` |
| a pasta de modelos ausente do pacote **e** criada na instalação | `test_a_pasta_de_modelos_nasce_ao_lado_do_exe_e_nao_dentro`, `test_nenhum_peso_entrou_dentro_do_pacote` |
| o `.iss` referencia arquivos que existem | `test_todo_arquivo_de_origem_citado_pelo_iss_existe`, `test_a_licenca_mostrada_e_um_arquivo_que_o_bundle_carrega` |
| o teto **afirmado**, não suposto | `TestTeto` (três testes, e a variante leve agora existe para o do meio afirmar algo) |
| a guarda da spec (herdada do tronco) | `TestSpec` (sete testes) |

Além disso: a regra de `excludes` conferida contra a medição
(`test_nenhum_exclude_e_um_modulo_vivo`), os hashes do manifesto reconferidos contra os
arquivos do tronco, e o download por HTTP recusado antes de tocar a rede — porque os `.pt`
são pickles do torch e canal não autenticado seria execução de código remoto.

**Resultado com os dois bundles no disco:**

```
> .venv\Scripts\python.exe -m pytest tests/integration/test_packaging.py -q
....................................................                     [100%]
52 passed in 1.04s
```

**52 passados, 0 pulados.** Sem build nenhum eles são 41 passados e 11 pulados, cada pulo
dizendo qual comando o destrava — e isso é deliberado: um teste verde que nunca viu um
bundle não diz nada sobre o bundle.

**Três destes testes existem porque um defeito escapou primeiro**, e essa é a única razão
honesta para um teste nascer depois do código:

| teste | o defeito que ele agora impede |
|---|---|
| `test_o_torchvision_levou_a_extensao_nativa` | bundle sem `_C_stable.pyd`, janela morta no `import` |
| `test_o_tkinter_levou_a_extensao_nativa` | `tkinter` só como `.py`, Pillow derrubada, fita sem ícones |
| `TestJanelaNaoTrava` (2 testes) | exceção num `.exe` sem console = caixa modal que ninguém fecha |

### 7.1 A suíte inteira — o portão de não-regressão

```
> .venv\Scripts\python.exe -m pytest -q
1 failed, 3100 passed, 1 skipped in 992.47s (0:16:32)
```

O portão da frente era **3022 passados, 1 pulado, 0 falhados**. Os 3.100 passados incluem os
52 desta frente e o que outras frentes acrescentaram no mesmo dia. O 1 pulado é o mesmo de
sempre (`test_fonts.py`: WOFF2 precisa do compressor Brotli, ausente neste ambiente).

**A falha não é desta frente, e vale dizer como isso foi verificado em vez de afirmado:**

```
FAILED tests/unit/ui/test_medicao.py::TestOperacoesDeFundo::
       test_a_coluna_determinada_e_a_faixa_do_widget_e_nao_o_argumento
```

O teste exercita `src/caissa/ui/audit/progresso.py`. Esse arquivo foi modificado às **15:19
de hoje** — depois da minha última alteração —, e `src/caissa/ui/` é justamente o diretório
que a regra desta frente proíbe tocar, porque outro agente está trabalhando nele em
paralelo. Os arquivos da suíte alterados hoje são `src/caissa/ui/audit/*` (cinco),
`src/caissa/typeset/board_svg.py`, `tests/unit/ui/*` e `tests/unit/typeset/*` — nenhum meu —
mais `tests/integration/test_packaging.py`, que é meu.

Numa passagem anterior da suíte, `tests/unit/ui/test_contraste.py` também falhou (2 falhas,
8 erros) e **passou inteiro minutos depois**, sem que nada mudasse do meu lado: era o mesmo
agente editando `ui/folha_de_estilo.py` do tronco durante a corrida.

**O que esta frente afirma, então:** os 52 testes de empacotamento passam, e nada em
`packaging/`, `LICENSING.md` ou `tests/integration/test_packaging.py` toca o que falhou. A
confirmação final de 3.10x/0/1 depende de o agente da F9 terminar o que está no meio.

---

## 8. O que **não** foi verificado

Esta seção existe porque as coisas abaixo são exatamente as que quebram na máquina de
outra pessoa, e nenhuma delas foi testada aqui.

1. **O instalador nunca foi compilado.** O Inno Setup **não está nesta máquina** (procurei em
   `C:\Program Files\Inno Setup 6`, `C:\Program Files (x86)\Inno Setup 6` e no `PATH`). O
   `installer.iss` está escrito para compilar e os testes conferem que cada caminho que ele
   cita existe — **mas ninguém o viu compilar.** O número de 169,3 MB (e o de 79,1 MB da leve) é um
   **proxy medido**: um `.7z` LZMA2 sólido da `dist/`, que é literalmente a compressão que o
   `[Setup]` pede (`Compression=lzma2/max`, `SolidCompression=yes`). O `setup.exe` real
   acrescenta o stub do Inno (~1,2 MB) e os arquivos de idioma. O arquivo diz isso na
   primeira tela e um teste afirma que diz.

2. **Não há assinatura de código.** Os dois `.exe` são **não assinados**. O SmartScreen vai
   avisar na primeira execução em qualquer máquina que não seja esta. Resolver exige um
   certificado de assinatura, que é uma decisão e uma despesa do dono do projeto. O
   `PrivilegesRequired=lowest` do `.iss` existe para não empilhar um segundo obstáculo em
   cima desse.

3. **Nunca rodou numa máquina Windows limpa, sem Python.** Tudo aqui foi executado na
   máquina que tem cinco Pythons, o CUDA, o tronco e os venvs. O `--onedir` do PyInstaller é
   feito para isso e o `_internal/` carrega `python311.dll`, mas **a afirmação "roda numa
   máquina sem Python" não foi testada** — ela é a promessa do PyInstaller, não uma medição
   desta frente. O teste que faltaria é copiar `dist/Caissa/` para uma VM limpa e rodar
   `CaissaPrimeiraExecucao.exe`.

4. **A variante leve foi construída e medida, mas não abre.** `ModuleNotFoundError: No
   module named 'torch'` — §3. Ela serve para medir o custo do torch, e é isso que ela fez;
   como produto ela depende de uma mudança em `qt/`, que não é desta frente.

5. **O caminho de download nunca tocou a rede.** `manifesto.json` tem `base_url: null`
   porque **não há servidor de distribuição publicado**. `caissa_modelos.baixar()` está
   escrito e testado no que dá para testar sem servidor (recusa de HTTP, verificação antes de
   renomear), mas nenhum byte foi baixado. O caminho que funciona hoje é a instalação
   offline, e o assistente diz isso em vez de fingir uma tentativa de rede.

---

## 9. Diário de disco (SPEC R4)

| momento | GB livres em C: |
|---|---:|
| antes de tudo | **48,67** |
| antes do build final (completo) | 46,05 |
| depois do build final (completo) | 45,89 |
| depois do build da variante leve | **45,43** |

`build_windows.py` **recusa começar** com menos de 6 GB livres, e grava os dois números no
`bundle.json`. O motivo é que um PyInstaller que enche o disco no meio da coleta deixa uma
`dist/` pela metade que parece pronta.

Consumo total desta frente: **3,24 GB**, para dois bundles, dois arquivos comprimidos e um
venv de empacotamento. Fica tudo apagável: `.venv-pack` (~1,1 GB), `build/` (intermediários
do PyInstaller), `dist/` (os dois bundles e os dois `.7z`).

Uma decisão de disco que vale registrar: o `.venv-pack` leva **torch de CPU** e não o cu128
do `.venv` principal. Só essa escolha poupou **3,7 GB** no ambiente de empacotamento
(506,1 MB contra 4.214,4 MB) — numa máquina em que a SPEC R4 chama disco de restrição
crítica, isso é mais do que uma conveniência.
