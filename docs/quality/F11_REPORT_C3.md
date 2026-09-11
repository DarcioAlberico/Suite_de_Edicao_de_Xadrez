# F11 ciclo 3 — `repair_ocr_region`, a quinta tarefa, medida; e ela não entra como texto

> **Data:** 2026-09-11 · **Máquina:** a de referência da SPEC §2 (Ryzen 5 8400F, 31,6 GiB,
> RTX 5060 8 GB `sm_120`, driver 591.86, Windows 11 Pro 26200).
> **Modelo:** `gemma4:e4b-it-qat` · **Servidor:** Ollama 0.34.0 · `think=false`, esquema
> JSON forçado, `seed` fixo por passada, `num_ctx=4096`. **OCR:** Tesseract 5.5.0, o único
> motor da cascata instalado nesta máquina (níveis 2 e 3 — RapidOCR, Paddle, Surya — ausentes).
>
> **Regra deste relatório:** todo número veio de um comando executado nesta máquina hoje
> (`benchmarks/reports/llm_i_c3.json`, `benchmarks/bench_llm.py --experiments i --repeats 3`).
> A §8 lista o que **não** foi medido.

---

## 0. Conclusão em uma tela

| Tarefa | Veredito | O número que decide |
|---|---|---|
| `repair_ocr_region` como **substituto automático** do texto da região | **NÃO ENTREGUE** | nas 70 regiões que a cascata rejeitou, o modelo **conserta 69 lances e quebra 2** — mas escreve **103 lances que não estão na página**. Em digitalização histórica (D3) ele acerta 80 lances e erra 88: mais lances errados com cara de certos do que certos |
| `repair_ocr_region` como **sugestão editável** na fila de revisão | possível, **não recomendado** | o ganho real está só em D3 (CER 0,38 → 0,26); em digitalização limpa ou ruidosa (D1, D2) o modelo devolve o texto do Tesseract praticamente intacto — 52 de 71 regiões iguais |
| A dica do OCR no prompt | **é o que sustenta o resultado** | sem a dica, o CER mediano nas regiões rejeitadas sobe de **0,036 para 0,258** e os lances inventados triplicam (103 → 309). O modelo copia o Tesseract e retoca; ele não lê a imagem sozinho |
| Confiança declarada pelo modelo | **não informa nada** | 291 de 317 respostas vêm com confiança ≥ 0,9; nessa faixa o P90 do CER é **0,27**. O portão de 0,40 barrou 3 respostas em 317 |
| Controle ilegível (D4) | **passa** | em 36 chamadas sobre ruído puro, 3 passaram pelo portão — mediana de **2 caracteres**, zero lances. O modelo não inventa parágrafos do nada |

Com isto, **as cinco tarefas da F11 estão medidas**. Placar final: uma entregue
(`translate_notation_prose`), uma entregue como sugestão editável (`caption_for_diagram`),
três não entregues (`verify_diagram`, `extract_stipulation` com LLM, `repair_ocr_region`).
A função `repair_ocr_region` **continua existindo e continua desligada**: o nível 4 nunca foi
registrado na cascata (`caissa/ocr/engines/registry.py`), e este ciclo não o registra.

Dois defeitos no portão da função foram encontrados pela medição e estão em §6; nenhum muda o
veredito.

---

## 1. O que este ciclo mediu, e contra o quê

A tarefa é o nível 4 da SPEC §7.1: uma região de texto que todos os motores de OCR leram com
escore abaixo do limite, entregue ao modelo com a imagem e com a leitura ruim, para
transcrição. Para medi-la são necessários três ingredientes: a imagem da região, **o texto
que está de fato impresso nela**, e um jeito de fazer a cascata rejeitá-la.

### 1.1 A verdade: onde a camada de texto do PDF *não* serve

A ideia óbvia — usar a camada de texto de PDFs nativos digitais como verdade — quebrou no
primeiro levantamento, e a razão é um achado por si só:

**Quase todo livro nativo digital do acervo usa fonte figurina cuja camada de texto não
corresponde à tinta.** O Dvoretsky (2025) diz `Kb7` na camada onde a página imprime ♔b7; o
Tesseract, lendo a página limpa a 300 dpi, devolve `2b7`. O Nunn diz `•d5+` e `]5+`. O
Schiller, o Karpov e o Zhuravlev têm lixo (`\IId2+`, `CZJd5`) no lugar de cada peça. O
Aagaard imprime `f4+` e a camada diz `f4t`. O Fischer em português usa figurinas Unicode
reais (♗g5), que nenhum OCR lê como letra.

`benchmarks/corpus/derived/build_ocr_regions.py` aplica por isso **dois filtros**, e só
sobrevive a região em que a camada e a tinta concordam:

1. **Léxico** — nada de code point privado ou U+FFFD, nenhum lance mutilado
   (`caissa.ocr.lexicon.mangled_move_ratio`), nenhum símbolo ou dígito solto colado a uma
   casa, letras de peça só as do idioma (`KQRBN`, `RDTBC`, `KDTLS`), ao menos 3 lances e
   4 palavras.
2. **Empírico** — o Tesseract lê a região **limpa**, a 300 dpi, com CER ≤ 0,02 **e o mesmo
   multiconjunto de lances** da camada. Se não lê, a verdade não bate com a página e a
   região cai.

O segundo filtro introduz um viés que precisa ficar dito: **o estrato real só contém fontes
que o Tesseract lê bem quando limpas.** É o preço de ter verdade verificada.

| Livro | idioma | regiões | por que tão poucas |
|---|---|---:|---|
| Xadrez Vitorioso — Finais (Seirawan) | pt | 30 | notação por letra, fonte comum: o único livro que rende em volume |
| Secrets of Chess Training School | en | 5 | só regiões sem letra de peça sobrevivem |
| Nunn — Secrets of Minor Piece Endings | en | 4 | idem |
| Dvoretsky — Endgame Manual | en | 3 | figurina: 197 regiões descartadas pelo filtro empírico |
| Melhores Finais de Capablanca (hq) | pt | 2 | |
| Aagaard — Practical Chess Defence | en | 1 | |
| Euwe & Kramer — Band 1-2 | de | 1 | camada de OCR de terceiros: 150 descartadas |
| **estrato real** | | **46** | 246 lances, 140 com letra de peça (todos em pt) |

Rejeições do levantamento, para o crítico: 38 543 grupos de linhas fora do tamanho, 1 263
sem lances suficientes, 616 fora do alfabeto, 516 com glifo colado a casa, 447 reprovados no
filtro empírico, 359 mutilados, 144 por nome de fonte, 62 por letra de peça de outro idioma.

### 1.2 O estrato sintético: para medir letra de peça em inglês

Como o estrato real não tem **nenhuma** letra de peça em inglês, um segundo estrato
contorna a tinta: `build_ocr_synth.py` colhe parágrafos de livros nativos digitais com os
mesmos filtros léxicos (sem o empírico) e o benchmark os **tipografa** com fontes de texto
comuns (Times, Book Antiqua, Georgia, Constantia, Calibri, alternadas), 10,5 pt, coluna de
3,9″, 300 dpi. A verdade é exata por construção. O que se perde é ser página de livro.

| Livro | idioma | parágrafos |
|---|---|---:|
| Dvoretsky — Endgame Manual | en | 30 |
| Xadrez Vitorioso — Finais | pt | 30 |
| **estrato sintético** | | **60** — 876 lances, 610 com letra de peça |

Nunn, Burgess, Secrets of Chess Training e Capablanca deram zero aqui: parágrafos curtos
demais ou sem duas jogadas de peça sadias na camada.

### 1.3 A degradação: três níveis medidos, um de controle

Cada região é renderizada a 300 dpi em cinza e degradada para **um** nível, escolhido pela
posição na lista, de modo que cada nível vê os dois estratos e os dois idiomas principais:

| nível | dpi | desfoque σ | ruído σ | inclinação | JPEG | tinta desbotada | regiões | rejeitadas pelo árbitro |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D1 digitalização limpa | 200 | — | — | — | 60 | — | 36 | 12 |
| D2 digitalização ruidosa | 150 | 0,9 | 12 | 0,6° | 45 | 15 % | 35 | 23 |
| D3 histórica | 110 | 1,2 | 18 | −1,0° | 35 | 35 % | 35 | 35 |
| D4 ilegível (controle) | 45 | 2,5 | 25 | — | 30 | 40 % | 12 | 12 |

"Rejeitada" é a decisão real do árbitro (`caissa.ocr.arbiter.Arbiter`) com o Tesseract como
único motor: escore total < 0,78. **Só nessas 70 regiões a produção chamaria o modelo**, e
são elas que decidem.

### 1.4 Os braços

- **`tesseract`** — o que a cascata entrega hoje nesta máquina.
- **`llm_hint`** — `repair_ocr_region(imagem, texto_do_tesseract)`, o caminho de produção,
  com os portões da função (confiança ≥ 0,40, comprimento ≤ 4× a dica, mínimo 80).
- **`llm_blind`** — a mesma chamada com dica vazia, para saber se a dica ajuda ou ancora.
- **`*_raw`** — as respostas antes dos portões, para julgar os portões.

O benchmark chama o modelo pelo mesmo `guarded_json_call` da função, com a confiança exposta,
e reaplica os portões em espelho. O espelho foi conferido contra a função real em 6 regiões
da primeira passada: 1 divergência, com os dois lados respondendo e o mesmo prefixo de texto
— é o modelo variando entre duas chamadas iguais, não o espelho.

**Pontuação.** CER (Levenshtein / tamanho da verdade) sobre texto normalizado — NFKC,
hífen e aspas unificados, hífen suave da camada tratado como o hífen impresso, `0-0` → `O-O`,
espaços colapsados. E a contabilidade de lances, que é o que importa num livro de xadrez:
para cada região, o multiconjunto de tokens com forma de lance da verdade contra o da
resposta — **mantidos**, **perdidos**, **inventados** (na resposta, não na página: lidos
errado ou fabricados, indistinguíveis para quem lê o livro). E, do Tesseract para o modelo,
**consertados** (o Tesseract errou, o modelo acertou) e **quebrados** (o inverso).

Mediana de 3 passadas, `seed` = número da passada (CORPUS.md regra 1). As três passadas
deram CER mediano idêntico; a variação ficou nos lances inventados (99, 103, 115).

---

## 2. O veredito: as 70 regiões rejeitadas

| braço | respondeu | CER mediana | CER P90 | CER média | lances da verdade | mantidos | inventados |
|---|---:|---:|---:|---:|---:|---:|---:|
| `tesseract` | 70 | 0,085 | 0,467 | 0,189 | 899 | 50,1 % | 18 |
| `llm_hint` (produção) | 69 | **0,035** | 0,363 | 0,130 | 899 | **58,8 %** | **103** |
| `llm_blind` (sem dica, sem portão) | 66 | 0,258 | — | — | 899 | 40,9 % | 309 |
| `llm_blind` (sem dica, com portão) | **2** | | | | | | |

**Produção** (resposta do modelo onde ele respondeu, Tesseract onde não):

| | valor |
|---|---:|
| CER mediana antes → depois | 0,085 → **0,036** |
| CER média antes → depois | 0,189 → 0,135 |
| regiões melhores / piores / iguais | **37 / 7 / 24** |
| lances consertados | **69** |
| lances quebrados | **2** |
| lances inventados | **103** |

Lidos em isolamento, os números da esquerda dizem "entregar": CER cai à metade, 69 lances
consertados por 2 quebrados. O número da direita diz o contrário, e é ele que manda: **o
modelo escreve 103 tokens com forma de lance que não estão na página**, contra 18 do
Tesseract — em **30 das 70 regiões**, contra 11 em que o Tesseract faz o mesmo. O Tesseract, quando erra um lance, produz lixo (`2b7`, `l:th7`) que o léxico da
F5 marca como mutilado e a fila de revisão exibe. O modelo, quando erra um lance, produz
`Kf5` — legal, plausível, invisível. É a lição do ciclo 2 (`extract_stipulation`) na
mesma forma: **um erro com cara de acerto é pior que um erro com cara de erro.**

---

## 3. Por nível: o ganho está todo em D3, e é onde o modelo mais inventa

| nível | n | CER Tesseract | CER produção | melhores/piores/iguais | consertados | quebrados | inventados (Tess → LLM) | mantidos (Tess → LLM) |
|---|---:|---:|---:|---|---:|---:|---|---|
| D1 limpa | 36 | 0,003 | 0,003 | 2 / 2 / 32 | 3 | 1 | 1 → 2 | 93,2 % → 93,7 % |
| D2 ruidosa | 35 | 0,010 | 0,007 | 10 / 5 / 20 | 11 | 1 | 18 → 16 | 78,8 % → 81,7 % |
| D3 histórica | 35 | **0,382** | **0,259** | 31 / 2 / 1 | **63** | 0 | **4 → 88** | 3,4 % → 21,1 % |

Em D1 e D2 — o que uma digitalização de livro normalmente é — o modelo devolve o Tesseract
praticamente intacto: 52 de 71 regiões idênticas, ganho de CER na terceira casa decimal,
14 lances consertados por 2 quebrados. Não há o que entregar.

Em D3 o modelo faz diferença, e nos dois sentidos. Dos 379 lances impressos, o Tesseract
mantém 13; o modelo mantém 80 — e escreve **88 que não estão lá**. Por região, são 2,5
lances errados com forma de lance. A saída do modelo em D3 tem **mais lances errados do que
certos**. Uma amostra, `synth:Dvoretsky :82` (D3):

```
página   : g4 b5 g5 b4 g6 b3+ Kc3 b2 g7 b1=Q g8=Q+ Ka1
tesseract: (nenhum token com forma de lance)
modelo   : g4 h5 g5 b4 h3 f4 c2 b3 b4 b3 h2 Kg8        <- 6 consertados, 6 inventados
```

E o pior caso, `synth:Dvoretsky :103` (D3), CER 0,39 no Tesseract e **0,83** no modelo:

```
página   : a5 Kg7 Kf4 Kf6 Ke4 Kf7 Kd5 Kf6 Kc6 Kxf5 Kb6 Ke6
modelo   : f4 Kf6 Kf4 Kf4 Kf5 Kf6 Kf6 Kf5 Kf5 Kf6 Kf6 Kf5 ...  <- 37 inventados
```

É o modelo entrando em repetição (`Kf5 Kf6 Kf5 Kf6…`) — com confiança declarada 0,9, e
passando pelo portão de comprimento porque a resposta tem só **1,16×** o tamanho da
verdade: a repetição *substituiu* o texto em vez de alongá-lo. Ver §6.2.

---

## 4. A dica é o resultado: o modelo não lê a imagem, retoca o Tesseract

O braço cego responde à pergunta "quanto disto é visão?". Sem a dica, nas regiões
rejeitadas, o CER mediano vai de 0,036 para **0,258** e os inventados de 103 para **309**.
Por nível, os lances mantidos sem dica ficam **abaixo do Tesseract** em D1 (65 % contra 93 %)
e D2 (52 % contra 79 %); só em D3 empatam (25 % contra 21 % com dica), ao custo de 151
inventados.

Ou seja: nos casos em que o modelo "acerta", ele acerta porque copiou a dica e corrigiu uma
ou duas letras. Isto é coerente com o ciclo 1 (`verify_diagram`): a torre visual do E4B não
lê detalhe fino de imagem de xadrez — nem casas, nem letras pequenas de notação.

Com portão, o braço cego responde **2 vezes em 70** — não porque o modelo cala, mas porque
com dica vazia o teto de comprimento da função cai para 80 caracteres (§6.1).

---

## 5. Confiança e controle

### 5.1 A confiança declarada não separa nada

| confiança declarada | respostas | CER mediana | CER P90 |
|---|---:|---:|---:|
| [0,0, 0,4) | 3 | 0,264 | 0,271 |
| [0,4, 0,6) | 0 | — | — |
| [0,6, 0,8) | 14 | 0,380 | 0,469 |
| [0,8, 0,9) | 9 | 0,195 | 0,565 |
| **[0,9, 1,0]** | **291** | 0,009 | **0,270** |

O modelo diz "0,9 ou mais" em 92 % das respostas, incluindo as de D3 com CER de 0,27 no
P90. O portão de 0,40 da função barrou 3 respostas em 317. Uma confiança que não varia não
pode alimentar a fila de revisão — a região transcrita pelo modelo chegaria ao usuário como
"0,9", igual a uma região limpa.

### 5.2 D4: sobre ruído puro, o modelo quase sempre cala

12 regiões degradadas até a ilegibilidade, 3 passadas, 36 chamadas: o Tesseract rejeitou as
12; o modelo devolveu texto que passou pelo portão em **3** chamadas (8 %), com mediana de
**2 caracteres** e **zero** tokens de lance; a confiança mediana foi 0,0. Este é o
comportamento pedido pelo prompt e é o único lugar em que a confiança declarada
funcionou. Vale registrar como o contrário do que aconteceu na §3: o modelo inventa
quando há *algo* legível para ancorar, não quando não há nada.

---

## 6. Dois defeitos do portão, encontrados pela medição

Nenhum altera o veredito; os dois estão registrados aqui para o dia em que a função for
ligada como sugestão.

### 6.1 Com dica vazia, o teto de comprimento é 80 caracteres

`repair_ocr_region` calcula `teto = max(80, 4 × len(dica))`. Quando a cascata devolve texto
vazio para a região — o caso mais provável de uma região realmente ruim — qualquer
transcrição com mais de 80 caracteres é descartada. O braço cego mostrou o efeito: 66
respostas cruas, **2** aprovadas — e foi conferido à mão em 8 regiões rejeitadas: confiança
0,9, decisão `accepted`, 126 a 316 caracteres contra um teto de 80. A intenção do teto (barrar o modelo que narra em vez de
transcrever) é boa; a base do cálculo precisa ser a **área da imagem** (caracteres esperados
por polegada quadrada), não a dica.

### 6.2 Repetição não é comprimento

O caso `synth:Dvoretsky :103` da §3 — 37 lances inventados em ciclo `Kf5 Kf6 Kf5…`, CER
0,83 — tem razão de comprimento **1,16** sobre a verdade e 305 caracteres de página.
Nenhum teto de comprimento o pega, por mais apertado que seja: o modelo não narrou a mais,
ele trocou o parágrafo por um ciclo do mesmo tamanho. O que pega é um detector de repetição
— razão de tokens distintos sobre o total, ou trigrama repetido ≥ 3 vezes — e é barato.
`caption_for_diagram` escapa deste modo de falha por ter `max_length` de 200; aqui o texto
é longo por natureza.

---

## 7. O que foi ligado, e o que ficou desligado

### 7.1 Ligado

Nada. `repair_ocr_region` continua sem registro na cascata, como estava.

### 7.2 Novo no repositório

- `benchmarks/corpus/derived/build_ocr_regions.py` → `llm_ocr_regions.jsonl` (46 regiões,
  só texto e coordenadas; nenhuma imagem sai do acervo).
- `benchmarks/corpus/derived/build_ocr_synth.py` → `llm_ocr_synth.jsonl` (60 parágrafos).
- `benchmarks/bench_ocr_repair.py`, experimento **I** de `bench_llm.py`
  (`--experiments i`, `--regions N`).
- `benchmarks/reports/llm_i_c3.json` — o relatório completo, com **uma linha por região**
  (`per_region_first_pass`) para que o crítico discorde região a região.

### 7.3 Desligado, por medição

`repair_ocr_region` como texto automático — §2. Quinta otimização rejeitada por medição
nesta frente (após TTA, temperatura calibrada, `verify_diagram`, `extract_stipulation`
com LLM).

---

## 8. O que **não** foi medido

1. **Digitalização real.** Todo o "escaneado" deste ciclo é degradação sintética de um
   render limpo. Um scan de 1956 tem sangramento de verso, curvatura de lombada, tinta
   irregular por caractere — nada disto está em D1–D3. A degradação foi escolhida para
   *parecer* com os estratos E2/E3 do CORPUS.md, não medida contra eles. O acervo não tem
   scan com verdade de campo.
2. **O estrato real está concentrado num livro.** 30 das 46 regiões são do Seirawan. É a
   consequência direta do achado da §1.1, e não tem remédio dentro do acervo atual.
3. **Alemão, russo, espanhol, neerlandês e francês não foram medidos.** 1 região em
   alemão; zero nos outros. Os livros desses idiomas no acervo são todos digitalizações com
   camada de OCR de terceiros, que reprova nos filtros.
4. **Figurinas não foram medidas.** O modo de impressão mais comum nos livros modernos
   (♔b7) ficou de fora por construção — nem a verdade nem o Tesseract o cobrem. Se um dia
   um motor ler figurinas, esta medição não diz nada sobre ele.
5. **Regiões de prosa pura.** Toda região tem ao menos 3 lances; um parágrafo só de prosa
   não foi medido, e é onde um modelo de linguagem levaria vantagem sobre o Tesseract.
   Não é o caso de uso da SPEC §7.1 nível 4, que é notação.
6. **Um só motor na cascata.** Com RapidOCR/Paddle/Surya instalados, o conjunto de regiões
   rejeitadas seria outro, e menor. O que foi medido é o que esta máquina faz.
7. **`gemma4:12b-it-q4_K_M` continua sem medição**, pelo terceiro ciclo. Ele está instalado
   e, carregado pelo usuário com contexto de 262 k, ficou a 56 % CPU / 44 % GPU (`ollama ps`
   no início do ciclo) — não cabe na placa, e o portão da F11 (≤ 7,0 GB com a visão ativa)
   o exclui por construção. A recomendação do ciclo 2 (§10) permanece: remover.
8. **O parâmetro `language` recebe o código (`pt`, `en`)**, não o nome, como o benchmark faz
   e como qualquer chamador faria; a função não documenta qual espera.
9. **Os filtros do levantamento foram escritos por este agente** e o corpus não passou por um
   segundo par de olhos. As linhas de `llm_ocr_regions.jsonl` estão lá com a verdade ao lado
   das coordenadas, para que o crítico as abra no PDF e discorde.

---

## 9. Reprodutibilidade

```
python benchmarks/corpus/derived/build_ocr_regions.py benchmarks/corpus/derived/llm_ocr_regions.jsonl
python benchmarks/corpus/derived/build_ocr_synth.py   benchmarks/corpus/derived/llm_ocr_synth.jsonl
python benchmarks/bench_llm.py --experiments i --repeats 3 --json benchmarks/reports/llm_i_c3.json
```

Levantamento: ~4 min (Tesseract a 300 dpi em cada candidato). Benchmark: 24 s de
Tesseract, 11 min de modelo (676 chamadas, mediana 1,17 s cada, modelo residente).
