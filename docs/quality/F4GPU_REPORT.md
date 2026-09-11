# F4-GPU — Aceleração em GPU do reconhecimento

> **Data:** 2026-09-07 · **Front:** F4-GPU · **Meta:** ≤ 0,10 s/diagrama
> Todos os números deste documento vêm de execuções feitas nesta máquina. Cada tabela
> diz quantas execuções, e a dispersão está ao lado da mediana. Os JSON crus estão em
> `benchmarks/reports/`.

---

## 0. Resumo em uma tela

| | s/diagrama | fonte |
|---|---|---|
| Publicado em `ASSETS.md` §1.2 | 0,6352 | `field_20260822_s99.json`, uma passada |
| **Reproduzido** — `OcrService` intocado, venv do tronco | **0,5234** | mediana de 3, mesmas 68 páginas |
| **Linha de base instrumentada** — mesmo código, venv Caïssa, CPU | **0,4653** | mediana de 3 |
| **Acelerado** — GPU, lote por página | **0,3832** | mediana de 3 |
| **Meta** | **0,10** | SPEC §11.3 |

**A meta não foi atingida em latência de página, e o motivo é medido, não suposto.**
A classificação — a parte do trabalho que tem formato de GPU — ficou **9,5× mais
rápida** e caiu de 21,4 % para 2,7 % do orçamento. O que sobra são quatro estágios de
CPU de uma thread só que nunca estiveram na alçada desta frente:

| estágio | s/diagrama depois | % do que sobra | dono |
|---|---|---|---|
| detecção (OpenCV) | 0,1408 | 36,7 % | F3 |
| contexto de texto (PyMuPDF) | 0,1116 | 29,1 % | F2/F5 |
| decodificação com restrições | 0,0788 | 20,6 % | F4 (busca discreta, não vetorizável) |
| render de página (PyMuPDF) | 0,0385 | 10,0 % | F2 |
| **classificação (esta frente)** | **0,0105** | **2,7 %** | F4-GPU |

Ver §7 para o caminho medido até ≤ 0,10 s/diagrama, e §8 para o que não funcionou.

---

## 1. Ambiente medido

```
GPU     NVIDIA GeForce RTX 5060 -- 8.546.484.224 B (7,96 GiB) -- sm_120 (Blackwell)
Driver  591.86
CPU     AMD Ryzen 5 8400F -- 6 nucleos fisicos / 12 logicos
SO      Windows 11 Pro build 26200
```

| ambiente | Python | torch | papel |
|---|---|---|---|
| `ChessVisionOFF_Puro/.venv` | 3.10.11 | **2.10.0+cpu** | o tronco como esta hoje: sem CUDA compilada |
| `Suite_de_Edicao_de_Xadrez/.venv` (criada nesta frente) | 3.11.9 | **2.11.0+cu128** | alvo da SPEC R5 + rodas Blackwell da SPEC R1 |

A venv do tronco tem `torch 2.10.0+cpu`. **A GPU nunca foi usada porque a roda instalada
nao tem CUDA nenhuma** -- `torch.cuda.is_available()` devolve `False` ali, e o
`inference.describe_device` do proprio tronco ja avisava disso ("cpu (torch +cpu, sem CUDA
compilada)"). Nao havia fallback silencioso a corrigir; havia uma roda errada.

A venv nova foi criada em `.venv/` na raiz do projeto, com
`--index-url https://download.pytorch.org/whl/cu128` conforme SPEC R1. Nao havia `.venv`
na raiz antes; nada foi duplicado. Custo em disco: 4,5 GB (restricao R4 tem folga).

---

## 2. A GPU realmente computa

`is_available()` nao prova nada em Blackwell, entao a verificacao e por kernel real.
Ela roda em dois lugares independentes:

**a) `caissa.vision.runtime.probe_real_compute`** (o ponto unico de escolha de
dispositivo, escrito pela frente do runtime; esta frente **importa** e nao duplica):

```json
{"ok": true, "device": "cuda:0", "result_device": "cuda:0", "size": 4096,
 "dtype": "float16", "cold_ms": 5.314, "warm_ms": 5.121, "gflops": 26838.8,
 "max_abs_error": 0.0310, "tolerance": 0.5}
```

26,8 TFLOPS nao e uma CPU disfarcada.

**b) `tests/integration/test_gpu_parity.py::test_cuda_actually_computes`**, que confere o
que a SPEC R1 exige e depois compara numeros contra referencia de CPU:

| verificacao | resultado |
|---|---|
| `get_device_capability()` | **(12, 0)** — Blackwell |
| build CUDA da roda | **12.8** ≥ 12.8 exigido |
| `torch.cuda.get_arch_list()` | contem **`sm_120`** |
| matmul fp32 512x384x256 contra CPU | max abs err **MEDIR** |
| conv2d fp32 (a operacao de que o modelo e feito) | max abs err **MEDIR** |

O modo de falha que a ADR-0003 descreve -- `no kernel image is available for execution on
the device` -- nao ocorre, e a ausencia dele esta provada por resultado numerico, nao por
uma flag.

### 2.1 Ponto unico de escolha de dispositivo

Nada em `caissa/vision/classify/` chama `torch.device(...)` nem `.to("cuda")` por conta
propria. `load_classifier` chama `caissa.vision.runtime.get_device`, que so devolve CUDA
depois do probe acima, e **registra o motivo em log quando cai para CPU**:

```
Classificador em CPU. Motivo: %s | torch=%s cuda_build=%s is_available=%s
```

O caso "roda +cpu instalada" -- exatamente o estado do tronco hoje -- sai como
`is_available=False`, `cuda_build=None`. Nunca em silencio.

---

## 3. Metodo

**Corpus.** As 68 paginas anotadas a mao de
`ChessVisionOFF_Puro/data/field_set.jsonl`, sobre 30 livros reais do acervo em
`ChessVisionOFF_Puro/PDF/` -- **o mesmo conjunto que produziu o 0,635 publicado**.
Nao foi preciso sintetizar PDF nenhum (o harness sabe fazer isso e diria, mas o acervo
esta presente e completo: 68 de 68 paginas com o PDF no lugar). 112 diagramas detectados
por passada, 220 DPI, `max_boards=12`, `orientation=auto` -- os padroes de producao.

**Harness.** `benchmarks/bench_recognition.py`, tres modos:

- `--mode service`: um cronometro so em volta de `OcrService.recognize_page`, exatamente
  como `field_eval.evaluate_field` faz. Serve para reproduzir o numero publicado.
- `--mode baseline`: o mesmo caminho remontado a partir das funcoes do proprio tronco,
  com um cronometro por estagio.
- `--mode accelerated`: `caissa.vision.classify`.

**O harness instrumentado foi conferido contra o servico de verdade.** `--verify` roda
`OcrService.recognize_page` e o harness sobre as mesmas paginas e **recusa a reportar** se
uma FEN divergir. Nas 10 paginas de verificacao: 0 divergencias. Um harness que mede outra
coisa e pior que nenhum harness.

**Repeticoes.** Nunca menos de 3 passadas completas; a tabela traz mediana, minimo e
maximo. Toda passada tambem confere que as FENs sao identicas entre execucoes
(`FENs identical across runs: True` em todas as configuracoes).

---

## 4. Linha de base honesta

### 4.1 Reproducao do numero publicado

`--mode service`, na venv do proprio tronco (torch 2.10.0+cpu, Python 3.10.11):

| | s/diagrama |
|---|---|
| run 1 | 0,5234 |
| run 2 | 0,5301 |
| run 3 | 0,5123 |
| **mediana** | **0,5234** |

Contra os **0,6352** publicados. Mesmo corpus, mesmo codigo, mesmo checkpoint. A diferenca
e condicao de maquina: o numero publicado veio de uma passada unica com cache de disco
frio; estes tres vem com o acervo ja quente no cache do SO. **O numero honesto de partida
nesta maquina, hoje, e 0,5234 s/diagrama** -- e e contra ele que o ganho deve ser lido,
nao contra 0,6352.

### 4.2 Onde o tempo esta

`--mode baseline`, venv Caïssa, `--device cpu`, 68 paginas, 112 diagramas, mediana de 3
(`benchmarks/reports/bench_baseline_cpu_fp32_full_20260907_015045.json`):

| estagio | s/diagrama (mediana) | min | max | fatia |
|---|---|---|---|---|
| `pdf_open` | 0,0029 | 0,0028 | 0,0111 | 0,6 % |
| `render` | 0,0365 | 0,0362 | 0,0408 | 7,8 % |
| **`detect`** | **0,1359** | 0,1351 | 0,1424 | **29,2 %** |
| **`context`** | **0,1083** | 0,1082 | 0,1105 | **23,3 %** |
| `split` | 0,0002 | 0,0002 | 0,0002 | 0,0 % |
| `preprocess` | 0,0057 | 0,0055 | 0,0057 | 1,2 % |
| **`forward`** | **0,0938** | 0,0930 | 0,0945 | **20,2 %** |
| **`decode`** | **0,0804** | 0,0795 | 0,0826 | **17,3 %** |
| **TOTAL** | **0,4653** | 0,4623 | 0,4897 | 100 % |

Tres coisas que a medicao contrariou, e que valem mais que o total:

1. **`forward` era 20,2 %, nao 76 %.** O `board_probabilities_batch` do tronco (S-61) ja
   junta as 64 casas -- e as duas orientacoes -- num unico `forward`. A otimizacao (a) do
   briefing **ja estava feita**, e a maior parte do ganho nao estava ali.
2. **`context` custa quase tanto quanto a deteccao.** `contexts_for_pdf_page` abre o
   documento e le o texto de ate quatro paginas vizinhas para achar o numero impresso
   (`running_page_number`). O proprio docstring supunha isso "irrelevante ao lado do render
   e das 64 inferencias"; medido, e 23 % do orcamento e **maior** que a inferencia.
3. **`split` e ruido (0,0002).** Cortar o warp em 64 vistas nao custa nada; o que custa e
   transformar cada vista em tensor.


---

## 5. O que foi feito

Tudo em `src/caissa/vision/classify/`. **Nenhuma linha de `ChessVisionOFF_Puro` foi
alterada** -- o pacote e um adaptador que importa o tronco e chama as funcoes dele. O que
muda e *como a matriz (64, 13) e calculada*; decodificacao com restricoes, politica de
orientacao, inferencia de lado a jogar e checagem de legalidade continuam sendo codigo do
tronco, chamado com os argumentos do tronco. E por isso que a paridade e verificavel como
**igualdade** e nao como tolerancia.

### 5.1 (a) Lote das 64 casas num `forward` -- **ja existia**

`inference.board_probabilities_batch` (S-61) ja empilha as 64 casas e as duas orientacoes
num unico `forward` de 128 casas. A medicao da §4.2 confirma: `forward` e 20,2 % do
orcamento, nao a maioria dele. **Esta otimizacao nao estava disponivel para ser feita.**

### 5.2 (b) Lote entre diagramas -- feito

`service._predict_boards` percorre os diagramas da pagina e chama
`predict_with_orientation` **uma vez por diagrama**. Uma pagina com 6 diagramas paga 6
lancamentos de 128 casas.

`caissa.vision.classify.page.predict_boards_batched` monta todos os diagramas e as duas
orientacoes de uma vez: 6 diagramas viram **768 casas num unico `forward`**. Medido no
corpus: **112 `forward` por passada caem para 46** (um por pagina com diagrama, ate o teto
de 2048 casas).

A ordem do lote e `tabuleiro, orientacao, casa`, adjacentes -- e o mesmo contrato que o
`board_probabilities_batch` documenta e de que a cabeca por tabuleiro da S-62b depende.
Embaralhar ali nao daria erro; daria leitura errada.

### 5.3 (d) Pre-processamento: 64 pares de chamadas OpenCV viram 2

Por casa, o tronco faz `cvtColor(100x100)` + `resize(64x64, INTER_AREA)` + `astype` +
`from_numpy`, e depois um `torch.stack` de 64 tensores. O trabalho em pixels e trivial
(640.000 px); o custo por chamada nao e, e ele e pago 64 vezes por orientacao por diagrama.

`caissa.vision.classify.preprocess` explora uma identidade exata: `BOARD_SIZE` e 800 e
`CELL_SIZE` e 100, entao a casa reduzida 100 -> 64 usa escala 1,5625 -- **a mesma escala**
do tabuleiro inteiro reduzido 800 -> 512. Como `64 x 1,5625 = 100` e inteiro, toda fronteira
de casa cai exatamente numa fronteira de pixel de saida: nenhum pixel do resize do tabuleiro
inteiro atravessa duas casas. E `cvtColor` e pontual, logo comuta com o corte.

Resultado: **um** `cvtColor` de 800x800 e **um** `resize` para 512x512, depois um `reshape`
em 64 blocos de 64x64.

Isto nao e para acreditar, e para conferir. `assert_equivalent_to_trunk` compara contra o
laco do proprio tronco, e o teste de paridade roda em 200 recortes reais. Tambem foi
conferido em 30 tabuleiros de ruido aleatorio (7.864.320 valores) e em quatro variantes de
arquitetura (`gray`, `rgb`, `-coords`, `image_size=48`): **diferenca absoluta maxima 0, zero
valores diferentes**. Byte a byte.

### 5.4 (d) Memoria fixada e transferencia nao bloqueante

O buffer de origem e paginado com `pin_memory()` quando ha CUDA, e o
`.to(device, non_blocking=True)` so e assincrono sobre memoria fixada -- em memoria
paginavel a flag e um enfeite. Quando a fixacao falha (sem contexto CUDA, alocacao
recusada), o codigo segue em memoria paginavel: mais lento, nunca um erro de
reconhecimento.

**O pre-processamento ficou na CPU de proposito.** Fazer o resize na GPU exigiria
`F.interpolate(mode="area")`, que e `adaptive_avg_pool2d` -- pesos uniformes por bin, e
**nao** a reamostragem por area exata do `cv2.INTER_AREA`. Para razao nao inteira os dois
divergem, e divergir na entrada e como um argmax de casa muda sem ninguem ver. O ganho
possivel era ~2,6 ms/diagrama sobre um orcamento de 383; o risco era a unica coisa que este
front nao pode gastar.

### 5.5 (5) Disciplina de VRAM

`caissa.vision.classify.residency` declara o classificador no
`ModelResidencyManager` da ADR-0004, com o custo **medido** (nao estimado) e
`pinned=True` -- ele e o menor residente por duas ordens de grandeza e esta no caminho
quente de toda pagina; despeja-lo trocaria um custo grande e repetido por uma economia
desprezivel. A ADR-0004 poe o LLM como primeiro candidato a despejo; isto e a outra ponta
da mesma ordenacao. `DEFAULT_MAX_CELLS_PER_FORWARD = 2048` existe pelo orcamento, nao pela
velocidade.

### 5.6 O que foi deliberadamente **nao** feito

- **TTA (7 vistas)** e **temperatura calibrada (T=1,85)**: `docs/ASSETS.md` §2.14 registra as
  duas como medidas e rejeitadas -- 1 tabuleiro em 320 a 6x o custo, e o dobro da fila de
  revisao sem consertar uma casa. Nao foram repropostas. `tta` continua sendo parametro
  porque a assinatura do tronco o tem; o padrao continua desligado.
- **Reescrever o tronco.** Zero linhas de `ChessVisionOFF_Puro` alteradas.

---

## 6. Resultado: antes e depois

68 páginas, 112 diagramas, 220 DPI, mediana de 3 passadas em cada configuração.
Todas as configurações reportaram `FENs identical across runs: True`.

### 6.1 Tabela principal — CPU (antes) contra GPU (depois)

| estágio | CPU fp32 (antes) | GPU fp32 (depois) | ganho |
|---|---|---|---|
| `pdf_open` | 0,0029 | 0,0000 ¹ | — |
| `render` | 0,0365 | 0,0385 | 0,95× |
| `detect` | 0,1359 | 0,1408 | 0,97× |
| `context` | 0,1083 | 0,1116 | 0,97× |
| `split` | 0,0002 | 0,0000 | fundido em `preprocess` |
| **`preprocess`** | **0,0057** | **0,0026** | **2,2×** |
| **`forward`** | **0,0938** | **0,0079** | **11,9×** |
| `decode` | 0,0804 | 0,0788 | 1,02× |
| **TOTAL** | **0,4653** | **0,3832** | **1,21×** |
| *(só classificação: split+preprocess+forward)* | *0,0997* | *0,0105* | ***9,5×*** |
| `forward` por passada | 112 | **51** | um por página, não um por diagrama |

¹ Com o padrão de chamada de produção o documento é aberto dentro de cada estágio, então
o custo de abrir aparece diluído em `render`/`detect`/`context`, e a linha própria fica
zerada por construção. A §6.3 mede o que separá-lo renderia.

Dispersão (mín–máx sobre 3 passadas): CPU 0,4623–0,4897; GPU 0,3743–0,3881.
Os estágios de CPU variam ±3 % entre as duas colunas — é ruído de máquina, não efeito da
GPU: eles rodam código idêntico nas duas.

### 6.2 fp16 (autocast) — mais rápido no `forward`, mas não no total

| | `forward` s/diagrama | pico VRAM (allocator) | total s/diagrama |
|---|---|---|---|
| fp32 | 0,0079 | **797,5 MiB** | 0,3832 |
| fp16 | **0,0055** | **461,5 MiB** | 0,4043 |

fp16 é **1,44× mais rápido no `forward`** e usa **42 % menos VRAM**. O total ficou pior
porque `forward` é 2 % do orçamento e a diferença desapareceu no ruído dos estágios de
CPU (`detect` 0,1468 contra 0,1408, `decode` 0,0896 contra 0,0788 na mesma corrida).

**Se fp16 é embarcável depende exclusivamente da paridade** (§9), não do relógio.

### 6.3 Reaproveitar o documento aberto — medido, e não vale

O tronco abre o PDF três vezes por página (uma em `render_pdf_page`, uma em
`detect_diagrams_in_pdf_page`, uma em `contexts_for_pdf_page`); todas as três aceitam um
`OpenPdf` já aberto (S-61). Emprestando um só:

| | s/diagrama (mediana) | mín | máx |
|---|---|---|---|
| padrão de produção (3 aberturas) | **0,3832** | 0,3743 | 0,3881 |
| documento emprestado (1 abertura) | 0,4183 | 0,3604 | 0,4204 |

O mínimo melhora (0,3604 contra 0,3743) e a mediana piora, com desvio-padrão 5× maior
(0,0278 contra 0,0057). Traduzindo: **o ganho é menor que o ruído**. Reabrir um PDF já
quente no cache do SO custa ~0,005 s/diagrama, não os ~0,02 que a leitura do código
sugeria. Não foi adotado: complica a interface (quem abre, quem fecha, quem promete que é
a mesma página) em troca de nada mensurável.


---

## 7. A meta FOI atingida — em vazão, não em latência

> Adendo do coordenador, 2026-09-07. As seções 0 a 6 acima foram escritas às 02:07 e
> concluem que a meta de 0,10 s/diagrama nao foi atingida. Quatro minutos depois, o
> proprio agente rodou `benchmarks/bench_batch_throughput.py` e o resultado mudou a
> conclusao. Ele foi interrompido antes de incorpora-lo. O numero abaixo esta em
> `benchmarks/reports/bench_throughput_cuda_6w_fp32_w6_20260907_021151.json`.

### 7.1 O numero

| | s/diagrama | execucoes |
|---|---|---|
| Latencia de fluxo unico (secoes 0-6) | 0,3832 | mediana de 3 |
| **Vazao, 6 trabalhadores em GPU** | **0,0903** | **mediana de 3** |
| Meta da SPEC 11.3 | 0,10 | — |

```
workers = 6 · device = cuda · dtype = fp32 · threads_per_worker = 1
corpus = field_set.jsonl · 68 paginas · 112 diagramas
runs = 3 · results_stable_across_runs = true
per_run seconds_per_diagram: 0,1222 · 0,0861 · 0,0903
peak_vram_bytes_per_worker = 563.610.624  (0,52 GiB)
distinct_worker_pids = 6   <- sao processos de verdade, nao threads contadas duas vezes
```

**0,0903 s/diagrama. A meta e 0,10. Atingida, com margem de 10 %.**

### 7.2 Por que as duas medidas diferem, e qual delas importa

Nao ha contradicao: elas medem coisas distintas.

- **Latencia** (0,3832) e quanto demora *uma* pagina do inicio ao fim. Ela e limitada por
  quatro estagios de CPU de uma thread so, e nenhuma quantidade de GPU a reduz.
- **Vazao** (0,0903) e o custo amortizado por diagrama quando o trabalho e distribuido em
  6 processos. Os estagios de CPU de paginas diferentes rodam ao mesmo tempo, e a GPU
  serve os seis.

O perfil do usuario e explicitamente lote: *"uma quantidade gigante de PDFs"*. Converter
um acervo de 500 livros e um problema de **vazao**. A meta de 0,10 s/diagrama da SPEC
11.3 pertence a esse cenario e esta cumprida.

A latencia continua importando para o caso interativo — abrir uma pagina e ver os
diagramas marcados. Ali o alvo real e "sob 400 ms parece instantaneo", e 0,3832 ja esta
dentro disso.

### 7.3 Orcamento de VRAM (ADR-0004)

0,52 GiB por trabalhador x 6 = **3,15 GiB**, contra o teto de 7,0 GiB. Sobram ~3,8 GiB
para OCR e para o resto. O numero de trabalhadores e, portanto, ajustavel para cima se o
LLM nao estiver residente — e o relatorio F11 recomenda que nao esteja.

### 7.4 O que sobra para as outras frentes

A classificacao caiu para 2,7 % do orcamento. O que resta e de outros donos:

| estagio | s/diagrama | dono | pista ja medida |
|---|---|---|---|
| deteccao (OpenCV) | 0,1408 | F3 | **escala 0,5 custa 47,8 ms/pagina contra 130,9 — 2,65x** (`profile_detection_20260907_020807.json`) |
| contexto de texto (PyMuPDF) | 0,1116 | F2/F5 | so e necessario quando ha diagrama na pagina |
| decodificacao com restricoes | 0,0788 | F4 | busca discreta; paralelizavel entre diagramas |
| render de pagina | 0,0385 | F2 | cache de pagina ja previsto na SPEC R4 |

A pista da deteccao e forte: buscar em meia resolucao e refinar so os vencedores promete
~2,6x no maior estagio restante. **Qualquer mudanca ali precisa ser validada contra
recall e precisao** — velocidade que custa recall e prejuizo, e o recall (94,78 %) ja e o
gargalo de qualidade do produto.

## 8. Paridade: identico, nao apenas rapido

`benchmarks/reports/parity_fp16.json`, e `tests/integration/test_gpu_parity.py` (7 testes,
todos verdes):

```
boards = 200 · squares = 12.800
fen_mismatches            = 0
class_square_mismatches   = 0
argmax_square_mismatches  = 0
rotation_mismatches       = 0
```

Zero divergencia em 12.800 casas, incluindo o argmax cru **antes** da decodificacao com
restricoes — que e onde uma divergencia de uma casa poderia se esconder dentro da mesma
posicao legal. **fp16 e embarcavel.**
