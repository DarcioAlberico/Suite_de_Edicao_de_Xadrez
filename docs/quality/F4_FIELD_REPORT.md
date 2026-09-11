# F4 — Classificação em campo: por que `field_exact` não fechava

> **Data:** 2026-09-10 · **Frente:** F4 (Classificação) · **Papel:** construtor
> **Máquina:** RTX 5060 (sm_120), Python 3.11.9, torch 2.11.0+cu128
> **Conjunto:** `ChessVisionOFF_Puro/data/field_set.jsonl` — 68 páginas anotadas, 115
> diagramas. Nunca usado em treino; ver §7.

---

## 0. O resultado em uma tela

O `docs/ROADMAP.md` registrava **97,87 %** de diagramas perfeitos em campo contra meta de
98,0 %, e dizia — corretamente — que o número *"não se moveu em nenhuma variante de
detecção"*. Este relatório descobre por quê, e a resposta é mais estreita do que a frase
sugere.

`field_exact` é `exported_exact / exported_comparable`. Medido, esse denominador é **94**.
Os 97,87 % são **92 de 94**: o vão inteiro entre a medição e a meta são **dois diagramas**,
e um deles não está errado.

| | medido | n |
|---|---|---|
| `field_exact`, **régua como anotada** | **0,9787** | 92/94 |
| `field_exact`, **régua corrigida** (uma anotação provadamente errada, §3) | **0,9894** | 93/94 |
| meta | 0,9800 | |

**Nenhuma linha de código de classificação mudou para produzir esses dois números.** A
diferença entre eles é uma anotação errada no conjunto de campo, provada pelo texto do
próprio livro (§3.1). Dizer que "a otimização X levou o número a 98,9 %" seria falso, e
este relatório não diz isso.

O que sobra depois da correção é **um** diagrama exportado e errado, em um livro de fonte de
xadrez, e ele tem causa raiz medida (§4): uma lacuna de **estilo** do classificador, não de
recorte, não de degradação, não de decodificação.

Quatro alavancas foram medidas e **todas as quatro rejeitadas por medição**:

| alavanca | resultado |
|---|---|
| refino de recorte antes de classificar | `field_exact` **idêntico**, mediana de 3 (§5) |
| decodificação com restrições | fechada por construção: as duas leituras são **legais** (§4.1) |
| jitter / TTA | a leitura errada não se move em ±8 px, em 12 variantes (§4.1) — reconfirma `ASSETS.md` §2.14 |
| **gerador sintético + fine-tune** | **conserta a casa** e sobe cobertura de estilo de 0,757 para 0,953 em estilos reservados, **mas regride o laboratório** e faz o produto exportar 5 diagramas a menos (§6) |

O fine-tune também produziu o achado que provavelmente vale mais que a métrica: **um modelo
pior marca `field_exact = 1,0000`**, porque a métrica condiciona em ter sido exportado
(§6.5). Nenhum código de classificação em produção mudou nesta frente.

---

## 1. Como a medição é feita

Harness novo, `benchmarks/field_exact.py`. Ele não inventa métrica: chama
`chess_diagram_ocr.field_eval.evaluate_field`, o mesmo código que produziu
`field_20260822_s99.json`, e obedece a `docs/quality/CORPUS.md` §5:

- **Mediana de ≥ 3 execuções** (`--runs 3`, mínimo imposto pelo próprio script).
- **Recall e precisão sempre ao lado**, porque a detecção foi tocada pela `recall_pack`.
- **Por estrato** (`regime`) e **por livro**, nunca só a média.
- O harness **derruba a medição** se qualquer contagem mudar entre execuções idênticas: o
  reconhecimento não tem aleatoriedade, e um número que oscila é defeito, não ruído. As três
  execuções de cada linha abaixo saíram idênticas casa a casa.

Detecção usada: `caissa.vision.detect.recall.recall_pack()` — o que a F3 entregou e o que a
`ROADMAP` mede (recall 0,9913, precisão 1,0000).

### 1.1 A régua corrigida, e por que ela é auditável

`benchmarks/field_corrections.json` é uma **sobreposição**, não uma edição. O
`field_set.jsonl` do tronco continua exatamente como estava; a correção é aplicada em
memória, no momento da medição, carrega a evidência inteira dentro do arquivo, e o harness
**recusa aplicá-la** se a linha anotada não estiver mais na forma que a correção espera. E
os dois números saem sempre lado a lado — um número corrigido publicado sem o cru ao lado é
um número que ninguém pode conferir.

Barra de entrada nesse arquivo: prova documental do próprio livro, ou dois leitores
independentes mais um argumento de convenção de glifo que o leitor possa conferir no
recorte. **Um modelo preferir outra resposta não é evidência** — é o que está sendo medido.

---

## 2. A tabela de falhas — o artefato principal

`tools/f4_field_failures.py` roda o pipeline sobre as 68 páginas, casa cada detecção com a
anotação pela regra do próprio conjunto (IoU ≥ 0,5 em pontos do PDF, guloso) e, para todo
diagrama casado cuja FEN diverge, grava: o recorte que o classificador viu, a FEN lida, a
FEN de referência, **quais casas diferem**, a confiança de cada uma dessas casas, as três
classes mais prováveis do modelo nelas, se a decodificação com restrições consertou algo, a
fonte de detecção e o IoU do casamento.

De **96** diagramas anotados com posição de referência, **3** divergem. É a tabela inteira.

Tudo o que segue pode ser **olhado**, não só lido, em
`benchmarks/reports/f4_field_failures_20260910_024914/`:

| arquivo | o que mostra |
|---|---|
| `0{1,2,3}_*.png` | os três recortes como o classificador os viu (800×800) |
| `0{1,2,3}_*_page.png` | a página inteira com a caixa anotada (verde) e a detectada (vermelha) |
| `zoom_euwe_native.png` | a6/f2/g2 (disputadas) ao lado de d5/b3/h2/d6/g6 (peões), a 8× do PDF — §3.1(b) |
| `zoom_burgess_compare.png` | g3 e h2 (peões **brancos** em casa escura, ocos) contra e5 e a7 (damas **pretas**, preenchidas) — §4 |
| `zoom_model_view_a7_e5.png` | a7 e e5 em 64×64 cinza, que é literalmente a entrada do modelo |
| `failures.json` | tudo acima em número, mais os top-3 por casa |

| # | livro | pág. | estrato | casas erradas | conf. mín. | exportado? | **causa raiz** |
|---|---|---|---|---|---|---|---|
| 1 | Euwe & Kramer, *Das Mittelspiel* Band 7 (1958) | 40 | `scan-hachurado` | 3 (a6, f2, g2) | 0,944 | **sim** | **Erro de anotação no conjunto de campo.** O modelo está certo; ver §3.1 |
| 2 | Levenfis, *Cartea şahistului începător* (1962) | 150 | `scan-hachurado` | 3 (h8, c3, g1) | 0,068 | não | Falha real de classificação: degradação de impressão, peças em contorno sobre casa hachurada. **O portão barrou** |
| 3 | Burgess, *The Gambit Book of Instructive Chess* | 60 | `fonte` | 1 (e5) | **0,998** | **sim** | Falha real: **dama preta lida como dama branca**. Lacuna de estilo; ver §4 |

Três observações que a tabela já paga sozinha:

- **A falha 2 não afeta `field_exact`.** Ela foi barrada pelo portão de confiança
  (`min_confidence` 0,068 contra gate 0,80) e portanto não entra em `exported_comparable`.
  Ela afeta `conditional_exact`, que conta os 96 comparáveis independentemente do portão:
  93/96 = 0,9688 na régua como anotada, 94/96 = 0,9792 na corrigida. O pipeline se comportou
  corretamente: a leitura ruim foi para a fila de revisão, não para o PGN.
- **A falha 3 é a única leitura exportada e errada que resta**, e é confiantemente errada —
  0,998. Nenhum ajuste de portão a pega: subir o gate para 0,999 barraria essa e mataria
  dezenas de leituras corretas.
- **Nenhuma das três é de recorte.** IoU do casamento: 0,9999 / 1,0000 / 1,0000. As três
  vieram com o tabuleiro enquadrado.

### 2.1 Distribuição por estrato (régua corrigida, mediana de 3)

| estrato | anotados | casados | `exported_comparable` | exatos | `field_exact` |
|---|---|---|---|---|---|
| `vetorial` | 31 | 31 | 31 | 31 | **1,0000** |
| `scan-puro` | 45 | 44 | 35 | 35 | **1,0000** |
| `scan-hachurado` | 21 | 21 | 10 | 10 | **1,0000** |
| **`fonte`** | **18** | **18** | **18** | **17** | **0,9444** |
| `sem-diagrama` | 0 | 0 | 0 | 0 | — (mede falso positivo) |

**O déficit inteiro está no estrato `fonte`**, e é um diagrama. Os outros quatro estratos
estão em 100 %. A média (0,9894) esconde isso, que é exatamente o que a regra 4 de
`CORPUS.md` manda não deixar acontecer.

Repare também no `scan-hachurado`: 21 anotados, 21 casados, e só 10 chegam a
`exported_comparable`. Onze são barrados pelo portão. Esse estrato não tem problema de
**exatidão**, tem problema de **rendimento** — e é outra métrica (`export_rate`), fora do
escopo desta frente.

---

## 3. A anotação errada, e como se prova que é ela

### 3.1 Euwe & Kramer, *Das Mittelspiel* Band 7 (1958), p. 40

| | a6 | f2 | g2 |
|---|---|---|---|
| anotação | `p` (peão preto) | `P` (peão branco) | `P` (peão branco) |
| modelo (p) | `b` (0,9998) | `B` (0,9436) | `B` (0,9989) |

Quatro evidências independentes, e a primeira sozinha decide.

**(a) O texto do próprio livro.** A camada de texto da página 40, extraída com PyMuPDF,
imprime os lances que seguem o diagrama (Stellung 58, depois de 32...Sh6xg4):

```
33. Lf 2-d4      Tb8-b4
...
35. Tg7Xh7!      La6-b7
```

`L` = *Läufer* = **bispo**. O livro diz, em letra de fôrma, que há um bispo branco em **f2**
e um bispo preto em **a6**. Duas das três casas em disputa estão nomeadas pelo próprio
autor.

**(b) A convenção de glifo, conferível no recorte.** Renderizados a 8× do PDF, os glifos de
a6, f2 e g2 têm **aba larga sobre base alargada**; os de b3, d5, h2, d6, g6 e h7 têm
**cabeça redonda sobre base estreita**. As duas famílias não se sobrepõem. g2 carrega o
mesmo glifo que f2 e a6.

**(c) O segundo leitor.** `Chess_diagram_to_FEN` (arquitetura e treino não relacionados) lê
f2 e g2 como **oficiais** também — diz `R` onde o modelo de produção diz `B`. Isso é o modo
de falha conhecido dele neste livro: em *Das Mittelspiel* Band 1-2 p. 100 ele transforma os
**quatro** bispos da posição em torres (§3.2). Ele concorda que não são peões.

**(d) Material.** Com a anotação como estava, as brancas estariam **um cavalo atrás** numa
linha que o livro encerra com *"mit Figurengewinn"* (com ganho de peça) **para as brancas**.
Com a correção, o material fica nivelado: T+T+B+B+3P contra T+T+B+C+3P.

Este único diagrama vale 1,06 pp de `field_exact`, porque o denominador é 94.

### 3.2 A auditoria no sentido contrário — a que podia envergonhar

Achar só erros de anotação que **melhoram** o número não é auditoria. O conjunto de campo
foi semeado por `field_eval.draft_page`, que rascunha a partir da saída **deste modelo**;
um erro confiante que o revisor humano tenha carimbado conta hoje como **acerto**, e a
tabela da §2 é cega para ele por construção.

`tools/f4_annotation_audit.py` lê os 96 diagramas com o segundo leitor, sobre **os mesmos
recortes**, e classifica:

| | n |
|---|---|
| produção **e** segundo leitor concordam com a anotação | **88** |
| só a produção concorda (candidato a erro de anotação escondido) | **5** |
| só o segundo leitor concorda (erro do modelo de produção) | **1** |
| nenhum dos dois concorda | **2** |
| segundo leitor falhou | 0 |

Os **5 candidatos foram olhados um a um, e nenhum é erro de anotação**:

| livro | pág. | o que o segundo leitor diz | veredito |
|---|---|---|---|
| Vladimirov, *1000 Chess Problems* | 60 | 22 casas diferentes | leu o tabuleiro **girado**; erro dele |
| Euwe, *Mittelspiel* 1-2 | 100 | c8, e7, e3, e2: **todo bispo vira torre** | erro dele, sistemático neste livro |
| Levenfis | 150 (d1) | c8, b2, e2, f2: bispo→torre | mesmo modo de falha |
| Euwe, *Mittelspiel* 1-2 | 25 | c1: bispo→torre | mesmo modo de falha |
| Neumann (1870) | 25 (d2) | h1: `R`→`r` | troca de cor; erro dele |

O único caso em que **só o segundo leitor concorda com a anotação** é a falha 3 — o Burgess.
Ou seja: um modelo independente confirma que e5 é uma **dama preta**, contra a produção.

---

## 4. A única falha real que ainda custa: Burgess p. 60, casa e5

Lido `5r1k/q5pp/8/2pR**Q**3/8/1P4P1/2n1PpKP/5R2`,
referência `5r1k/q5pp/8/2pR**q**3/8/1P4P1/2n1PpKP/5R2` — dama branca onde há dama preta,
com **p = 0,9979** (segunda opção `q` = 0,0021).

A anotação já trazia a nota *"duas damas pretas; conferido casa a casa em e5 e a7 num
recorte de 200×200 por casa"*, isto é, um humano tinha conferido exatamente esta casa. Três
fontes independentes concordam com ele:

1. **A convenção da fonte.** Neste livro, peça **branca** sobre casa escura é desenhada
   **oca**: interior branco, contorno preto, a hachura interrompida em volta — é o que se vê
   nos peões brancos de g3 e h2, ambos em casa escura. O glifo de e5 é **preenchido**, com
   quatro fendas brancas de relevo dentro do corpo. Preenchido = preta.
2. **A dama de a7**, lida corretamente como `q` a 1,0000, é o mesmo desenho preenchido, sem
   as fendas de relevo.
3. **O segundo leitor** lê `q` (§3.2).

### 4.1 O que a causa **não** é — cada uma descartada por medição

| hipótese | teste | resultado |
|---|---|---|
| recorte desalinhado | IoU do casamento | **1,0000**; o embutido do PDF entrega o tabuleiro exato |
| grade fora de registro | classificar e5 com o tabuleiro deslocado ±2, ±4, ±8 px em x e em y (12 variantes) | `Q` em **todas as 12**, de 0,632 a 0,999. **Não é enquadramento** — e é o mesmo mecanismo que a TTA usa, o que reconfirma a rejeição de `ASSETS.md` §2.14 |
| as fendas brancas de relevo | fechamento morfológico da casa, k = 3, 5, 7, 9 | `Q` continua ganhando: 0,9985 → 0,9960 → 0,9831 → 0,9486. Contribuem, mas não explicam |
| decodificação com restrições poderia consertar | `check_position` nas duas leituras | **as duas são legais** (`is_fatal=False`, sem status). O decodificador nunca considera a alternativa — este caminho está fechado por construção |
| refino de recorte antes de classificar | `--variant recall-pack+refine`, mediana de 3 | `field_exact` **idêntico** (§5) |

### 4.2 O que a causa **é**: cobertura de estilo

`benchmarks/style_coverage.py` (novo) renderiza os 12 glifos de cada um dos **86 conjuntos
de peças** que o `Chess_diagram_to_FEN` traz, em casa clara e em casa escura — 2.064 glifos
limpos, centrados, em contraste cheio — e pede ao **modelo de produção** que os nomeie.

```
model piece_classifier.pt   sets 86   glyphs 2064
glyph accuracy 0.7548   sets read perfectly 22/86
```

E a confusão dominante, sobre 86 conjuntos independentes:

| confusão | ocorrências |
|---|---|
| **`q -> Q`** (dama preta → dama branca) | **48** |
| `p -> P` | 38 |
| `k -> K` | 33 |
| `r -> R` | 31 |
| `n -> p` | 27 |

**A falha mais comum do classificador, medida fora do acervo, é exatamente a falha de
campo que restou**, no mesmo sentido (preta lida como branca) e na mesma peça. O
`extra/condal` — uma fonte de diagrama de **livro**, não de tela — reproduz a leitura
`q -> Q` a **p = 0,9999**, em casa clara e escura.

### 4.3 A ressalva honesta que esse número carrega

O 0,7548 **não** quer dizer que o modelo seja fraco no que o produto lê. Os conjuntos que
ele erra são majoritariamente de tela e decorativos (`lichess/xkcd` 0,083, `lichess/horsey`
0,167, `extra/8_bit` 0,250), que não aparecem num PDF de livro de xadrez. As fontes de
**livro** do catálogo — `extra/book`, `extra/cases`, `extra/classic`, `extra/bases`,
`extra/vintage`, `lichess/merida`, `lichess/alpha`, `lichess/cburnett` — estão todas em
**1,000**.

Então a leitura correta da medição é mais fina: a cobertura de estilo *tipográfico* do
modelo é boa; o que falha, e falha em 45 dos 86 conjuntos, é a **decisão de cor da peça**
quando o desenho foge do que ele viu — e o `extra/condal`, que é uma fonte de livro, mostra
que a fronteira passa dentro do território do produto, não fora dele.

---

## 5. As alavancas medidas e rejeitadas

`benchmarks/field_exact.py --variant baseline --variant recall-pack --variant
recall-pack+refine --runs 3 --corrections` — mediana de 3, contagens idênticas nas três.

| variante | régua | recall | precisão | exportados | `exported_comparable` | exatos | `field_exact` | s/diagrama |
|---|---|---|---|---|---|---|---|---|
| tronco puro | como anotada | 0,9478 | 0,9732 | 100 | 94 | 92 | 0,9787 | 0,3755 |
| tronco puro | corrigida | 0,9478 | 0,9732 | 100 | 94 | 93 | **0,9894** | 0,4410 |
| `recall-pack` | como anotada | 0,9913 | 1,0000 | 102 | 94 | 92 | 0,9787 | 0,5104 |
| `recall-pack` | corrigida | 0,9913 | 1,0000 | 102 | 94 | 93 | **0,9894** | 0,4697 |
| `recall-pack` + refino | como anotada | 0,9913 | 1,0000 | 102 | 94 | 92 | 0,9787 | 0,4876 |
| `recall-pack` + refino | corrigida | 0,9913 | 1,0000 | 102 | 94 | 93 | **0,9894** | 0,4538 |

**Refino de recorte (`RecognitionOptions.refine_detected_boards`): sem efeito nenhum.**
Mesmos 94/94, mesmas casas, mesmos diagramas. É a **quarta** otimização rejeitada por
medição neste projeto — junto de TTA e temperatura calibrada (`ASSETS.md` §2.14) e do
Gemma 4 E4B (`ROADMAP`). O fine-tune sintético da §6 é a quinta.

**Decodificação com restrições: fechada por construção neste caso.** As duas leituras do
Burgess são legais; o solucionador não tem sobre o que agir. Ele continua a valer o que
valia — 17 casas reparadas em 8 diagramas neste run —, mas nenhuma delas é uma das três
falhas.

Note também que **`s/diagrama` aqui não é a métrica de vazão do `ROADMAP`**: este harness
mede página inteira em processo único, e o 0,0903 publicado é da vazão em 6 processos na
GPU (`bench_throughput_cuda_6w_fp32_w6`). Os dois números medem coisas diferentes e não se
comparam.

---

## 6. O gerador sintético: portado, treinado, medido — e **rejeitado**

O `docs/ASSETS.md` §3 lista o gerador sintético como lacuna real da F4, e a §4.2 deste
relatório é a medição que aponta a alavanca. Ele foi portado, treinado duas vezes e medido
nos três eixos. **Nenhuma das duas receitas é adotável**, e a razão é instrutiva.

### 6.1 O que foi portado

`src/caissa/vision/train/synthgen.py` — **adaptador, não cópia**. As primitivas de render
(86 conjuntos de peças, temas de tabuleiro, warp projetivo por peça, deslocamento de matiz,
fundos procedurais) são chamadas no clone original; o que o adaptador acrescenta é o que o
treino deste projeto exige e o gerador de origem não oferece:

1. **Escolha explícita do conjunto de peças.** `generate_one` sorteia entre os 86. Medir
   generalização exige separar estilos de treino dos de avaliação, e um sorteio não permite.
2. **Sem rede.** `_overlay_random_text` do original chama `_download_google_fonts`, que
   **baixa fontes da internet**. Este acervo não sai da máquina e este processo não busca
   nada: a sobreposição de texto usa fontes locais do Windows, e vem desligada por padrão.
   Fixado em teste, sobre a árvore sintática e não sobre o texto do arquivo.
3. **Rótulo no vocabulário do tronco**, `BOARD_SIZE = 800` e FEN de colocação.
4. **Determinismo por índice**: a amostra `n` com semente `s` é sempre a mesma imagem. É o
   que torna um dataset sintético reproduzível **sem gravar um único PNG** — 2.500
   tabuleiros são 655 MiB de RAM e **zero bytes em disco**.

`src/caissa/vision/train/finetune.py` é o harness: casas reais do split `train` de
`splits.csv` (4.117 tabuleiros legíveis, 263.488 casas) **mais** casas sintéticas dos
conjuntos de treino, partindo do checkpoint de produção. Cinco arquivos de `data/samples/`
citados em `labels.csv` não abrem e são pulados com aviso — vale registrar para quem for
mexer no dataset do tronco.

### 6.2 As duas receitas

| | `f4` | `f4b` |
|---|---|---|
| tabuleiros sintéticos | 2.500 (57 conjuntos de treino) | 2.500 (mesmos) |
| épocas / lr / `real_repeat` | 3 / 3e-4 / 3× | 1 / 5e-5 / 8× |
| render | cor, temas de disco, matiz | **estilo impresso**: sem matiz, sem tema de disco |
| casas por época | 950.464 | 2.267.904 |
| tempo | 62 s render + 3 × 95 s treino | 106 s render + 236 s treino |

### 6.3 O que o gerador **conseguiu**: cobertura de estilo

`benchmarks/style_coverage.py --sets holdout` — **29 conjuntos de peças que nenhum dos dois
modelos viu**, 696 glifos limpos, os mesmos pixels para os três modelos:

| modelo | acurácia de glifo | conjuntos perfeitos | trocas preta→branca* |
|---|---|---|---|
| produção | 0,7572 | 10/29 | **49** |
| `f4` | **0,9526** | **21/29** | **2** |
| `f4b` | 0,9124 | 19/29 | **1** |

\* *mesma peça, cor invertida* (`q→Q`, `p→P`, `r→R`, …) nos 29 conjuntos reservados. Não
confundir com os 48 `q→Q` da §4.2, que são só a dama e são sobre os 86 conjuntos.

**+19,5 pontos percentuais em estilos nunca vistos**, e a confusão que causou a falha de
campo — preta lida como branca — cai de 49 para 2. A hipótese da §4.2 estava certa sobre o
mecanismo, e o gerador ensina exatamente o que se esperava dele.

E a casa e5 do Burgess, medida diretamente nos dois checkpoints sobre o **mesmo recorte**:

| modelo | e5 | a7 (controle) |
|---|---|---|
| produção | `Q` = 0,9979 ❌ | `q` = 1,0000 ✔ |
| `f4` | **`q` = 0,6999** ✔ | `q` = 1,0000 ✔ |

**A leitura foi corrigida.** A causa raiz identificada na §4 era a certa.

### 6.4 O que ele **custou**, e por que isso decide

`benchmarks/lab_gate.py --runs 3` — split `test` de `splits.csv`, 534 tabuleiros / 34.176
casas, contagens idênticas nas três execuções:

| modelo | decodificador | acurácia por casa | tabuleiros exatos | ≤1 erro | ilegais (argmax cru) |
|---|---|---|---|---|---|
| produção | com restrições | **0,999386** | **0,9775** | 533 | 0 |
| produção | argmax cru | 0,999327 | 0,9775 | 532 | 2 |
| `f4` | com restrições | 0,999151 | 0,9757 | 530 | 0 |
| `f4` | argmax cru | 0,999034 | 0,9738 | 530 | **4** |
| `f4b` | com restrições | 0,999064 | 0,9738 | 530 | 0 |
| `f4b` | argmax cru | 0,998947 | 0,9719 | 530 | **4** |

| candidato | Δ casa | Δ tabuleiro exato | Δ ilegais (cru) | veredito |
|---|---|---|---|---|
| `f4` | **−0,000234** | **−0,0019** | **+2** | **REGRESSÃO** |
| `f4b` | **−0,000322** | **−0,0037** | **+2** | **REGRESSÃO** |

A regra desta frente é explícita: *se uma mudança melhora `field_exact` mas custa acurácia
por casa ou legalidade, diga e descarte*. As duas custam as duas coisas. **As duas são
descartadas.**

Note que a receita **mais suave** regrediu **mais**. O ajuste não é de agressividade nem de
domínio de cor: é o dado sintético puxando o modelo para longe da distribuição real. Uma
terceira receita nesta direção não é apoiada por nada que eu tenha medido.

Com isso o fine-tune sintético entra na lista de `ASSETS.md` §2.14 como a **quinta**
otimização rejeitada por medição neste projeto. A diferença em relação às outras quatro é
que esta **funciona no mecanismo que se propôs a consertar** (§6.3) — o que a reprova é o
preço, não a hipótese. É por isso que a §8.2 sugere duas variantes específicas em vez de
arquivar a ideia.

> Nota de leitura: a acurácia por casa de produção aqui é 0,999386, e não os 0,999854 do
> `docs/BASELINE.md`. Não é regressão: aquele número é do split de teste de **320**
> tabuleiros da época; este é do split de teste **atual**, de 534. Os dois candidatos foram
> medidos contra a produção no mesmo split, no mesmo processo, que é a comparação válida.

### 6.5 A armadilha que este experimento expôs — e que vale mais que ele

Medido em campo com o candidato `f4` (`--runs 3`, régua corrigida):

| | produção | `f4` |
|---|---|---|
| `exported` | 102 | **97** |
| `export_rate` | 0,8870 | **0,8435** |
| `comparable` | 96 | 96 |
| `exact` | 94 | **92** |
| `conditional_exact` | 0,9792 | **0,9583** |
| `exported_comparable` | 94 | **89** |
| `exported_exact` | 93 | 89 |
| **`field_exact`** | 0,9894 | **1,0000** |

**O candidato marca `field_exact = 1,0000` lendo pior.** `exact` cai de 94 para 92 sobre os
mesmos 96 diagramas comparáveis; `conditional_exact` cai de 0,9792 para 0,9583. O que subiu
foi o denominador saindo: `field_exact` condiciona em *ter sido exportado*, então um modelo
menos confiante melhora nele deixando de exportar justamente o que erraria.

Por livro, o que sumiu:

| livro | exportados | corretos exportados |
|---|---|---|
| Schiller, *Big Book of Combinations* | 6 → 4 | **6 → 4** |
| Gunderam (1961) | 1 → 0 | **1 → 0** |
| Euwe, *Mittelspiel* Band 7 | 4 → 3 | 1 → 0 |
| Burgess, *Gambit Book* | 4 → 3 | 3 → 3 |

**Quatro** leituras **corretas** deixaram de chegar ao PGN — `exported_exact` cai de 93 para
89, e nenhuma das quatro era um erro. E o próprio Burgess p60 — o diagrama que motivou tudo
— passou de "exportado e errado" para "não exportado": a leitura agora é a **certa**
(`q` = 0,700), mas 0,700 está abaixo do portão de 0,80.

Isto é exatamente o que o docstring de `field_eval.field_exact` chama de *"uma catraca que
só desce"*. Um relatório que publicasse "o fine-tune levou `field_exact` de 97,87 % a
100 %" estaria certo na aritmética e errado em tudo o mais. **`field_exact` nunca deve ser
lido sozinho: `export_rate` e `conditional_exact` têm de estar ao lado dele.** Recomendo
que o `ROADMAP` passe a publicar os três juntos.

---

## 7. Disciplina de medição

- **O conjunto de campo nunca entrou em treino.** As casas reais do fine-tune vêm do split
  `train` de `splits.csv` (4.117 tabuleiros legíveis, 263.488 casas), que é estável por
  hash; o `field_set.jsonl` não é legível a partir do harness de treino.
- **Estilos são separados, não imagens.** `split_piece_sets` reserva 29 dos 86 conjuntos de
  peças. Treinar numa renderização de `lichess/alpha` e medir noutra renderização de
  `lichess/alpha` mediria memorização.
- **Mediana de ≥ 3** em toda medição de campo e de laboratório; os harnesses **recusam**
  `--runs` menor que 3 e derrubam a medição se as contagens divergirem entre execuções.
- **Recall e precisão sempre juntos**, e por estrato.
- **Nada foi escrito no tronco.** Nem no `field_set.jsonl`, nem em `labels.csv`, nem no
  `models/piece_classifier.pt`. A correção de anotação é uma sobreposição neste repositório,
  e os dois checkpoints candidatos ficam em `benchmarks/reports/f4_candidates/` — fora de
  `models/`, porque um checkpoint reprovado no portão guardado onde se procura o modelo de
  produção é um acidente esperando acontecer.
- **O portão decide antes do campo.** `lab_gate.py` roda primeiro e não sabe nada sobre
  `field_exact`; um treinador que também se avalia é como uma regressão é adotada.

### 7.1 Disco

| momento | livre | o que mudou |
|---|---|---|
| início dos trabalhos | **30,6 GiB** (32.822.403.072 bytes) | o briefing registrava ~31,5 GiB |
| depois das dependências do segundo leitor e do gerador | 28,9 GiB | `scikit-image`, `scipy`, `matplotlib`, `cairosvg` + `cairocffi`, `pyfastnoiselite`, `pyffish`, `tqdm`, `imageio`, `tifffile` — a `.venv` foi a 4,9 GiB |
| ao fim | **28,0 GiB** | ver abaixo |

O maior item é a instalação: sem `scikit-image`, `matplotlib`, `cairosvg` e
`pyfastnoiselite` **o segundo leitor não carrega** (`TsojUnavailableError`) e o gerador
sintético não roda — o adaptador `tsoj_reader.py` do tronco existia mas nunca tinha sido
exercitado nesta `.venv`. Elas são dependência real do que a §3.2 e a §6 medem; quem quiser
o disco de volta pode desinstalá-las e perde as duas capacidades.

> **Pendência declarada:** essas dependências foram instaladas na `.venv` e **não** estão
> declaradas no `pyproject.toml` — a frente F4 não tem permissão de editá-lo. Numa `.venv`
> nova, `tools/f4_annotation_audit.py`, `benchmarks/style_coverage.py` e
> `src/caissa/vision/train/` falham no import. Elas cabem num extra opcional (p. ex.
> `[project.optional-dependencies] research`), porque nenhuma é necessária para o produto
> rodar — só para reproduzir estas medições. Os testes novos pulam sozinhos quando o clone
> não está presente, então a suíte não depende disso.

Os ~900 MiB entre as duas últimas linhas são artefatos de medição, todos em
`benchmarks/reports/`, todos pequenos e todos deliberados:

| artefato | tamanho | por que fica |
|---|---|---|
| `f4_field_failures_20260910_024914/` | 8,9 MB | **a tabela de falhas com os recortes.** É o artefato principal desta frente |
| `f4_annotation_audit_20260910_030113/` | 7,9 MB | os 8 recortes de discordância da §3.2, para o crítico reconferir |
| `style_coverage_*/` | 1,3 MB | os três relatórios de cobertura de estilo |
| `f4_candidates/*.pt` | 17 MB | os dois checkpoints **não adotados**, para o crítico remedir a §6.4 sem retreinar |
| JSONs de `field_exact_*`, `lab_gate_*`, `f4_finetune_*` | < 1 MB | as medições |

**Os dois checkpoints ficam fora de `models/`, de propósito.** Um checkpoint reprovado no
portão guardado no diretório onde se procura o modelo de produção é um acidente esperando
acontecer.

Os 2.500 tabuleiros sintéticos são renderizados **em memória** e descartados: 655 MiB de RAM
e **zero bytes em disco**. Cada treino grava um único arquivo, o checkpoint (8,8 MB). Nada
mais foi gerado, e nada foi deixado em `/tmp` nem no tronco.

---

## 8. O que fica para quem vier depois

### 8.1 Ferramentas novas, todas repetíveis

| arquivo | o que responde |
|---|---|
| `tools/f4_field_failures.py` | *Quais diagramas de campo saem errados, e em que casas?* Grava recorte, FEN lida, FEN de referência, casas divergentes, confiança e top-3 por casa, IoU, fonte de detecção |
| `tools/f4_annotation_audit.py` | *A anotação está errada em algum lugar que me favorece?* Roda o segundo leitor sobre os mesmos recortes e faz a lista curta |
| `benchmarks/field_exact.py` | `field_exact` por estrato e por livro, mediana de ≥3, com as duas réguas lado a lado |
| `benchmarks/style_coverage.py` | Onde acaba a cobertura de estilo do classificador, sobre 86 conjuntos de peças, com metade reservada |
| `benchmarks/lab_gate.py` | O portão: nenhum candidato passa se custar acurácia por casa ou legalidade |
| `benchmarks/field_corrections.json` | As correções de anotação provadas, com a evidência dentro |
| `tools/f4_finetune.py` + `src/caissa/vision/train/` | O gerador sintético portado e o harness de fine-tune |
| `tests/unit/classify/` | 34 testes: o gerador (determinismo, separação de estilos, **offline**) e a régua corrigida (a correção ainda casa com a anotação, a posição corrigida é legal, as casas nomeadas são as que mudam) |

### 8.2 Recomendações, em ordem de valor

1. **Corrigir `field_set.jsonl` no tronco** — a linha de `Das Mittelspiel Band 7` p. 40,
   com a evidência de `benchmarks/field_corrections.json`. Enquanto ela não for corrigida,
   todo relatório de campo do projeto carrega 1,06 pp de erro para baixo. Não fiz a edição
   porque o conjunto de campo é a medição e não é meu para editar; a sobreposição está
   pronta e auditável.
2. **Publicar `field_exact` sempre com `export_rate` e `conditional_exact` ao lado** (§6.5).
   Sozinho, `field_exact` recompensa um modelo por deixar de exportar o que erraria, e a
   §6.5 tem o exemplo medido de um candidato marcando **1,0000** enquanto lê **dois
   diagramas a mais errados**.
3. **Crescer o conjunto anotado.** `CORPUS.md` §3 já pede 400 diagramas; o denominador de
   `field_exact` hoje é **94**, então **um diagrama vale 1,06 pp** e a meta de 98,0 % é
   decidida por um único tabuleiro. Nenhum trabalho de classificação é mensurável nessa
   granularidade — o intervalo de confiança de 93/94 é largo demais para separar 97,9 % de
   98,9 %. Esta é, disparado, a maior alavanca restante da F4, e é trabalho de anotação, não
   de modelo.
4. **Se voltar ao gerador sintético**, o caminho medido não é "mais dados": é *quais* dados.
   O que ele ensina bem, e ensina muito bem, é decisão de **cor de peça** fora da
   distribuição (49 → 2 trocas em estilos reservados). O que ele custa é a especificidade no
   estilo impresso do acervo. Duas hipóteses que este relatório **não** testou e que valem a
   próxima iteração: (a) congelar o tronco convolucional e ajustar só a última camada; (b)
   destilação — treinar o candidato para casar as **probabilidades** da produção nas casas
   reais, deixando o sintético mexer só onde a produção é incerta. As duas atacam a
   regressão da §6.4 diretamente, e as duas são mensuráveis com o portão que já existe.
5. **Não repetir**: refino de recorte (§5, sem efeito), TTA/jitter (§4.1, e já em
   `ASSETS.md` §2.14), decodificação com restrições para *esta* falha (§4.1, as duas
   leituras são legais).

### 8.3 O placar de reconhecimento, como fica

| métrica | meta | medido | régua |
|---|---|---|---|
| Acurácia por casa | ≥ 99,95 % | 99,9386 % (split de teste atual, 534 tabuleiros) / 99,9854 % (split histórico de 320, `BASELINE.md`) | — |
| Diagramas perfeitos (laboratório) | ≥ 99,0 % | 97,75 % (split atual) / 99,06 % (split histórico) | — |
| **Diagramas perfeitos (campo)** | **≥ 98,0 %** | **97,87 %** / **98,94 %** | como anotada / **corrigida** |
| Recall de detecção (campo) | ≥ 99,0 % | 99,13 % | — |
| Precisão de detecção (campo) | ≥ 98,5 % | 100,00 % | — |

As duas linhas de laboratório merecem atenção de quem cuidar do `ROADMAP`: medidas no split
de teste **atual** (534 tabuleiros), a produção dá 0,999386 por casa e 0,9775 por tabuleiro,
não os 0,999854 e 0,9906 publicados — que são do split de **320** da época do `BASELINE.md`.
Não é regressão do modelo; é o conjunto que cresceu. Mas os números publicados e o conjunto
de teste corrente já não são a mesma medição, e um dos dois precisa ser atualizado antes que
alguém compare os dois achando que compara modelos.

### 8.4 A suíte

```
QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q
3281 passed, 1 skipped, 3 warnings in 745.41s (0:12:25)   # com tests/unit/classify/test_synthgen.py
3289 passed, 1 skipped, 3 warnings in 724.77s (0:12:04)   # + tests/unit/classify/test_field_corrections.py
```

Código de saída 0 nas duas.

A linha de base era **3.255 passados, 1 pulado**; a primeira execução acima confirma isso
por subtração (3.281 − 26 testes novos = 3.255). O pulo é o mesmo de sempre e não é meu:
`tests/unit/typeset/test_fonts.py:333`, WOFF2 sem o compressor Brotli. Os 3 avisos são
`DeprecationWarning` do Pillow **dentro do clone `Chess_diagram_to_FEN`**
(`generate_chessboards.py:505`), disparados pelos três testes que renderizam um tabuleiro;
são de código de terceiro que não é meu para editar.

**Nenhum teste existente foi tocado.** Os 34 novos vivem todos em `tests/unit/classify/`.

### 8.5 Honestamente: o que esta frente mudou e o que não mudou

**Não mudou:** nenhuma linha do caminho de classificação em produção. As duas alavancas que
eu poderia ter ligado — refino de recorte e fine-tune sintético — foram medidas e
descartadas, uma por não fazer efeito e a outra por custar mais do que rende.

**Mudou:** o que se sabe. O vão de 0,13 pp para a meta eram **dois diagramas**, e um deles
está certo — a anotação é que estava errada, e isso é demonstrável pelo texto do próprio
livro. O que resta é **um** diagrama, com causa raiz medida e um caminho de correção que
funciona no glifo e ainda não fecha a conta no produto.

Se a régua for corrigida, `field_exact` é **98,94 %** e a meta de 98,0 % está cumprida. Se
não for, é **97,87 %** e não está. Os dois números estão nesta página, com o que os separa
inteiramente à vista, e não há terceira leitura.
