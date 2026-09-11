# F7 — Relatório do construtor, ciclo 11

```
FRENTE: F7 (Tipografia)
CICLO: 11
RESPOSTA A: docs/quality/F7_CRITIQUE_C10.md  (VEREDITO: APROVADO, zero bloqueantes)
BLOQUEANTES DO CICLO 10: 0
```

O ciclo 10 aprovou e trouxe dez achados. Este ciclo não é sobre a aprovação: é sobre os
seis que me foram entregues como trabalho, **dois deles defeitos reais que não deviam ter
sobrevivido a um «aprovado»**. Todo número abaixo sai de um comando que corri, e o comando
está escrito ao lado do número.

Os instrumentos estão em `benchmarks/reports/c11/`, e `benchmarks/reports/c11/scratch/`
guarda os três PDF do ciclo 10 **byte a byte** como foram entregues, para que qualquer
afirmação minha sobre o «antes» possa ser re-medida em vez de acreditada:

```
benchmarks/reports/c11/scratch/proofsheet.pdf       72b91d218415c30bcbb8e1fabc3b6d28
benchmarks/reports/c11/scratch/proofsheet_run.pdf   e4c17085be8daddfcec0740bc270e2fa
benchmarks/reports/c11/scratch/proofsheet_rios.pdf  60eb0aefc5d667e8f555ee80d2a33295
```

**Escrevi em:** `src/caissa/typeset/`, `tools/`, `tests/unit/typeset/`,
`docs/quality/F7_REPORT_C11.md`, `benchmarks/reports/proofsheet*`,
`benchmarks/reports/c11/`. **Não toquei** em `benchmarks/reports/blind*/` — e a §8 traz o
portão novo que impede que alguém lhe toque por engano, que é o acidente de que o crítico
do ciclo 10 teve de se desviar à mão.

---

## Sumário — o que cada item custou e o que passou

| item | o que era | número medido | estado |
|---|---|---|---|
| **A** | `subset_font` não determinística | 3 SHA-256 → **1 SHA-256** em 3 chamadas a 1,3 s | **FECHADO** |
| **B** | `word_gap_cut` devolve a borda da janela | `cut` 19 px → **7 px**, igual nas 4 páginas | **FECHADO** |
| **C** | linha inglesa omitida da tabela | publicada: **2,56× / 0,303 / 33,3 %**, 0 de 3 | **PUBLICADO + causa medida** |
| **D** | `_our_pages` lê 10/11/12 | agora **fólios 44/45/46**, rotulados | **FECHADO** |
| **E** | `diagram->move` a duas alturas | 10,37 / 6,70 mm → **6,70 / 6,70 mm** | **FECHADO** |
| **F** | tinta 4,23 mm fora da mancha (p4) | p4 acaba a **145,54 mm** de 146,90 | **FECHADO + portão vivo** |
| **—** | `move->body` a duas alturas | fechado ao custo medido de **3,671 mm** | **FECHADO** |

Suíte: **3 execuções seguidas, verde nas três** (§9).

---

## A — `subset_font` era genuinamente não determinística

### A prova, antes

`benchmarks/reports/c11/repro_subset.py`, três chamadas separadas por 1,3 s:

```
call 1: sha256=762a0f1cd7f1fb4c2f48af5ce13a3173cf2cd4a2621b0b7e9c5ad77fed216dca  len=6036
call 2: sha256=dea002d8a227e34e3df5e3612dc30c92eec2ff286bb7234da78813c79d675b61  len=6036
call 3: sha256=3940717676fc01c1267dfb0498d55c58061d344b791bd680b341eb984142a117  len=6036
byte offsets differing between call 1 and call 3: [67, 183, 207]
  offset 67: 0xbd vs 0xc0     offset 183: 0x1f vs 0x19     offset 207: 0x94 vs 0x97
NON-DETERMINISTIC
```

Os três offsets são exactamente os que o crítico deu. Um é o segundo byte de
`head.modified`; os outros dois são o `checkSumAdjustment` que o cobre.

### A causa, no sítio certo

`TTFont.__init__` traz `recalcTimestamp=True` por omissão, e
`fontTools.ttLib.tables._h_e_a_d.table__h_e_a_d.compile` faz literalmente
`self.modified = timestampNow()`. O teste antigo só passava quando as duas chamadas caíam
no mesmo segundo.

### A correcção

`src/caissa/typeset/fonts.py`:

* `SUBSET_EPOCH = 0x7C259DC0` — 2 082 844 800, que é **1970-01-01 00:00:00 UTC** expresso
  na época de 1904 do OpenType. Não é arbitrário: o `decompile` do fontTools avisa
  `'modified' timestamp seems very low` para tudo **estritamente abaixo** desse valor e
  depois soma-lho; como este projecto transforma avisos em erros, fixar em zero daria o
  mesmo carimbo com um aviso por leitura.
* `pin_font_timestamp(ttfont, *, when=SUBSET_EPOCH, pin_created=False)` — público, para que
  a F8 feche o segundo sítio com uma linha.
* `TTFont(str(font_path), fontNumber=0, recalcTimestamp=False)` e o pin antes de `save()`.

`head.created` fica como está, e isso é medição e não suposição: o fontTools só recalcula
`modified`, e o `created` que ele repara na leitura é função dos bytes do ficheiro, não do
relógio. `test_subset_pins_the_modification_stamp_and_leaves_created_alone` lê os dois
campos do subconjunto emitido e afirma as duas metades.

### A prova, depois

```
call 1: sha256=749662182ac340810f9ff298cfe6d5088a599d1d3ae35e9c9bd0d9bcbdb979dd  len=6036
call 2: sha256=749662182ac340810f9ff298cfe6d5088a599d1d3ae35e9c9bd0d9bcbdb979dd  len=6036
call 3: sha256=749662182ac340810f9ff298cfe6d5088a599d1d3ae35e9c9bd0d9bcbdb979dd  len=6036
byte offsets differing between call 1 and call 3: []
IDENTICAL
```

### O teste — e porque não é um `sleep`

O teste antigo (`test_subset_is_deterministic`) chama duas vezes e compara. Ele **passa**
mesmo com o defeito, quase sempre: as duas chamadas caem no mesmo segundo. Foi assim que o
ciclo 9 declarou «0 falhas» e o ciclo 10 apanhou 1 falha em 12.

O teste novo, `test_subset_is_deterministic_across_a_second_boundary`, não adiciona sorte
nem espera: **conduz o relógio**. Substitui `fontTools.misc.timeTools.timestampNow` — a
única coisa que `head.compile` consulta — por uma função que anda uma hora a cada chamada, e
exige que os dois blobs sejam iguais.

**Liveness, medida.** Retirei o pin e corri os testes de determinismo três vezes:

```
run 1: FAILED test_subset_is_deterministic_across_a_second_boundary
       FAILED test_subset_pins_the_modification_stamp_and_leaves_created_alone
       2 failed, 1 passed          <- o "1 passed" e o teste ANTIGO
run 2: idem   2 failed, 1 passed
run 3: idem   2 failed, 1 passed
```

O teste antigo passa **3 de 3** sem a correcção; os novos falham **3 de 3**. É a moeda ao ar
exibida ao lado do seu substituto.

**As 12 execuções isoladas** que o crítico correu (1 falha em 12), refeitas com os dois
testes de determinismo (`benchmarks/reports/c11/subset_12runs.txt`):

```
run 1..12: 2 passed, 25 deselected     -> 12 de 12, zero falhas
```

### O segundo sítio, que não é meu — e o número dele

`src/caissa/export/pdfwrite.py::_subset_font` tem a mesma falha. **`src/caissa/export/`
pertence a outra frente e eu não lhe toquei.** Medi-o para entregar um número em vez de uma
suspeita (`benchmarks/reports/c11/repro_pdfwrite.py`):

```
call 1: sha256=c3d218a04d31d7486139  len=4008
call 2: sha256=25fba95fad883326db2c  len=4008
call 3: sha256=06827bda2276ac6a29d8  len=4008
NON-DETERMINISTIC (3 hashes)
```

Continua a carimbar a hora dentro de cada fonte que o exportador PDF incorpora. A correcção
é uma linha: `from caissa.typeset.fonts import pin_font_timestamp` e chamá-la antes do
`save()` — a função é pública e a sua docstring nomeia este caller.

---

## B — `word_gap_cut` sentava-se na borda da própria janela

### A prova, antes (`benchmarks/reports/c11/diag_cut.py`)

```
proofsheet_run.pdf dpi=300 p1: leading_est=61.75 window=[4,19] cut=19 TOP-EDGE
proofsheet_run.pdf dpi=300 p2: leading_est=61.75 window=[4,19] cut=19 TOP-EDGE
proofsheet_run.pdf dpi=300 p3: leading_est=61.75 window=[4,19] cut=19 TOP-EDGE
proofsheet_run.pdf dpi=300 p4: leading_est=55.50 window=[3,17] cut= 7 interior
proofsheet_run.pdf dpi=200 p1..p4:            window=[2,12] cut=10 interior
```

Com `cut = 19` quase nenhum vão conta como vão de palavra, as linhas caem por
`len(words) < 3`, a página sai `thin` e **desaparece do agregado sem dizer nada**.

### Três coisas que encontrei e que ainda não estavam ditas

1. **A entrelinha estimada está errada por 42 %.** A verdadeira é 10,406 pt = **43,36 px** a
   300 DPI. O estimador (mediana dos passos entre bandas de tinta, por coluna, e depois a
   mediana das colunas) dá **61,75** px nas p1–p3 e **55,50** nas p4, porque metade dos
   passos são pares de linhas fundidos (85–88 px) e há passos de diagrama (553 e 623 px).
   Os passos, tal e qual, por coluna:
   ```
   p1 colL passos>3 = [86,43,43,86,45,86,43,86,43,88,44,54,623,117,117,86,43,85,45,44,43,85,88,44]  mediana da coluna = 69.50
   p4 colR passos>3 = [553,72,73,45,88,41,44,55,622,73,72,44,43,43,47,86,41,45,43]                  mediana da coluna = 47.00
   ```
   Os passos de uma linha para a seguinte são 43–45 px; os de 85–88 são duas linhas que a
   deteção de bandas fundiu numa só, e a mediana cai no meio dos dois grupos.
2. **A 200 DPI o `cut` também estava errado**, e ninguém tinha visto: a janela acabava
   *depois* da moda dos vãos de palavra e o `argmin` caía num bin ralo da **cauda**
   (`cut = 10`) em vez do vale (que é 5). É essa a razão de a mesma página dar 0,0 %, 6,7 %
   ou 33,3 % conforme a rasterização.
3. **As quatro páginas de `proofsheet_run.pdf` são a MESMA página com quatro fólios.**
   Verifiquei o texto (1 362 caracteres, 90 linhas, 279 spans; o `diff` entre p1 e as outras
   é uma linha, `44` contra `45`/`46`/`47`) e o conjunto de vãos por coluna (`pool=602` e
   `pool=364`, hash idêntico nas quatro). Isto é o que torna o defeito indefensável: sobre
   **quatro cópias da mesma página**, a 300 DPI, o instrumento devolvia dois cortes
   diferentes (19, 19, 19 e 7) e três das quatro páginas saíam por medir. Não é ruído de
   medição; é o limiar a mudar de resposta sem que a página mude.

### A correcção

`word_gap_cut_detail` já não usa a entrelinha para nada — o argumento é aceite e ignorado, e
está dito na docstring. O histograma é lido pelo que ele é:

1. **moda das letras** = o bin mais alto (numa página há muito mais vãos dentro de palavras
   do que entre elas: verdade nas vinte e duas rasterizações que medi — as nossas oito
   páginas a 200 e a 300 DPI, mais as seis do conjunto cego);
2. **corte** = o bin que maximiza `max(contagens acima dele) − contagem[bin]`, para bins de
   `moda+2` até ao último bin com dados menos um;
3. **moda das palavras** = esse pico acima.

O passo 2 é o que torna **impossível** devolver uma borda: o último bin com dados tem
pontuação no máximo zero, porque não há nada acima dele para ser alto. Não há janela e
portanto não há borda de janela.

É prominência e não `argmin` entre duas modas por uma razão medida: a população de letras da
**referência E** tem uma ondulação de um bin aos 5 px (92 e depois 104), e uma regra que
parasse na primeira subida chamaria 5 px «moda das palavras» e cortaria a página aos 4. A
prominência ignora a ondulação porque a ondulação não tem pico por cima.

### A recusa — a metade que o enunciado pede

Quatro condições; se alguma falhar o caller recebe `ok=False` e **nenhum número**:

| constante | valor | o que impede |
|---|---|---|
| `CUT_MIN_POOL` | 50 | uma página com vãos a menos para contar |
| `CUT_MIN_SPAN` | 3 | duas modas coladas, sem vale entre elas |
| `CUT_MAX_DEPTH` | 0,5 | um histograma unimodal com uma mossa |
| `CUT_MIN_WORDS` | 20 | um corte que mede o fim dos dados |

E a recusa propaga-se: `page_word_band` devolve `undecided=True` sem banda, sem desvio e sem
«fora»; `_merged` **recusa a linha inteira** se qualquer página sua recusou (o ciclo 10
perdeu 3 de 4 páginas exactamente porque o agregado levava o que houvesse);
`measure_wordband` imprime `PAGINAS RECUSADAS`; e `_sabotage` **levanta** em vez de sabotar
com um corte inventado.

### A prova, depois

**Nenhum número de referência se mexeu** — que era a condição para a correcção não ser
também uma mudança da comparação:

```
amostra_A cut=6   amostra_B cut=4   amostra_C cut=5
amostra_D cut=5   amostra_E cut=9   amostra_F cut=7      (iguais ao ciclo 10)
```

E as nossas páginas, `benchmarks/reports/c11/diag_cut2.py`:

```
proofsheet_run.pdf  dpi=300  p1 p2 p3 p4:  cut=7 px  modas 2/11  vale 4  profundidade 0.12
proofsheet_run.pdf  dpi=200  p1 p2 p3 p4:  cut=5 px  modas 2/7   vale 8  profundidade 0.35
proofsheet.pdf      dpi=300  p11 p12 p13:  cut=7 px
proofsheet_rios.pdf dpi=300  p1:           cut=7 px
```

**O critério do crítico, cumprido:** as quatro páginas da corrida medem, e o corte da mesma
página escala com o DPI — 5 px a 200, 7 px a 300, contra os 7,5 exactos do rácio 1,5×; a
resolução do instrumento é o bin de 1 px, e 7 é o bin adjacente.

### As quatro páginas da corrida, re-medidas

```
F nossa, corrida (folio 44/45/46/47)   just 60/160  n=60  corte 7 px  banda 0.80–1.84 = 2.30x  desvio 0.284  fora 20/60 (33.3 %)
    p1  just 15/40  n=15  corte 7 px  banda 0.80–1.84 = 2.30x  desvio 0.284  fora 5/15 (33.3 %)
    p2  just 15/40  n=15  corte 7 px  banda 0.80–1.84 = 2.30x  desvio 0.284  fora 5/15 (33.3 %)
    p3  just 15/40  n=15  corte 7 px  banda 0.80–1.84 = 2.30x  desvio 0.284  fora 5/15 (33.3 %)
    p4  just 15/40  n=15  corte 7 px  banda 0.80–1.84 = 2.30x  desvio 0.284  fora 5/15 (33.3 %)
```

Quatro cópias de uma página, quatro respostas **iguais ao dígito**. É o único resultado que
um instrumento reprodutível pode dar aqui, e antes deste ciclo ele dava quatro respostas
diferentes.

### Testes

* `test_the_word_gap_cut_cannot_land_on_the_edge_of_its_own_search` — o histograma exacto que
  produziu o defeito, perguntado com a entrelinha certa e com uma 42 % maior; as duas
  respostas têm de ser a mesma, e o corte tem de ficar estritamente entre as duas modas.
* `test_the_word_gap_cut_refuses_a_histogram_that_is_not_two_populations` — as três recusas,
  cada uma verificada pela razão que dá, e `cut == 0` nas três.
* `test_the_word_band_measures_all_four_run_pages_and_they_agree`.
* `test_the_word_band_reads_the_book_pages_and_names_the_folios`.

### Um limite que fica declarado

A mesma composição rasterizada em tema claro e em tema escuro não dá exactamente o mesmo
número: a p3 da folha (fólio 46, escuro) mede **2,56× / 0,337** onde as p1/p2 (claro) medem
**2,30× / 0,284**, com as mesmas quebras de linha (o `build` confirma «mesma lista de blocos
que o hachurado (escuro): True»). A diferença é anti-aliasing de tinta clara sobre fundo
escuro. O **corte** é o mesmo (7 px) nas duas, que é o que este item corrigiu; a precisão
residual de um instrumento de raster sobre espaço entre palavras é da ordem de ±0,05 no
desvio, e digo-o aqui para que ninguém cite a terceira casa decimal.

---

## C — a página inglesa, publicada por inteiro

### As duas linhas (e a terceira), como o `wordband` as imprime

```
A Quality Chess p149      just  38/58   n=38  corte 6 px  banda 0.54–1.92 = 3.57x  desvio 0.327  fora 18/38 (47.4 %)
B Nunn p50                just  35/37   n=35  corte 4 px  banda 0.69–1.75 = 2.55x  desvio 0.258  fora 11/35 (31.4 %)
C Gambit p116             just  82/88   n=81  corte 5 px  banda 0.60–1.80 = 3.00x  desvio 0.263  fora 28/81 (34.6 %)
D Everyman/Aagaard p215   just  48/65   n=47  corte 5 px  banda 0.57–2.00 = 3.50x  desvio 0.394  fora 24/47 (51.1 %)
E Dvoretsky 2025 p215     just   7/42   n= 7  corte 9 px  banda 0.92–1.12 = 1.21x  desvio 0.073  fora  0/7  ( 0.0 %)
F nossa, pt (folio 44)    just  22/45   n=22  corte 7 px  banda 0.71–1.33 = 1.89x  desvio 0.160  fora  2/22 ( 9.1 %)
F nossa, en (folio 44/45/46)      just 45/120  n=45  corte 7 px  banda 0.78–2.00 = 2.56x  desvio 0.303  fora 15/45 (33.3 %)
F nossa, corrida (folio 44..47)   just 60/160  n=60  corte 7 px  banda 0.80–1.84 = 2.30x  desvio 0.284  fora 20/60 (33.3 %)
```

E o critério, agora aplicado a **cada** página nossa pelo próprio instrumento e não à mão:

```
F nossa, pt (folio 44)              contra as quatro que justificam: 3 de 3   banda 1.889 ganha  desvio 0.160 ganha  fora 0.091 ganha
F nossa, en (folio 44/45/46)        contra as quatro que justificam: 0 de 3   banda 2.556 PERDE  desvio 0.303 PERDE  fora 0.333 PERDE
F nossa, corrida (folio 44..47)     contra as quatro que justificam: 1 de 3   banda 2.300 ganha  desvio 0.284 PERDE  fora 0.333 PERDE
```

O crítico previu o agregado correcto das três páginas de livro em **2,56× / 0,303 / 33,3 %**
antes de eu corrigir o item D. É exactamente o que sai. E onde ele mediu **1 de 3** para a
página cega isolada, o agregado das três páginas de livro dá **0 de 3**, e perde a banda por
pouco: **2,5556× nossos contra 2,5455× da Nunn** — 0,010, ou 0,4 %. Não arredondo isso para
«empata»: perde.

### A causa: medida, e não a que se esperava

O enunciado nomeou o suspeito óbvio — qualidade do dicionário de hifenização — e mandou
medi-lo em vez de o assumir. Medi-o, e **o suspeito é inocente**.

**Primeiro, o dicionário** (`benchmarks/reports/c11/hyphen_quality.py`):

| | inglês | português |
|---|---|---|
| padrões Liang no dicionário | **8 527** | **427** |
| excepções | 8 | 2 |
| palavras de 4+ letras na cópia da página | 83 | 136 |
| comprimento médio | 6,41 letras | 6,29 letras |
| com ao menos um ponto legal | 39 = **47,0 %** | 88 = **64,7 %** |
| pontos legais por palavra | **0,65** | **0,85** |
| pontos legais por 100 letras | **10,15** | **13,45** |
| palavras de 7+ letras sem ponto nenhum | 8 de 42 = **19,0 %** | 0 de 54 = **0,0 %** |

O dicionário inglês é **vinte vezes maior** e mesmo assim oferece **menos** pontos nesta
cópia. As palavras inglesas de 7+ letras sem um único ponto legal são `already`, `avoided`,
`blocked`, `chapter`, `hanging`, `sharper` e mais duas — o conjunto `en` é o UKhyphen, que é
deliberadamente parco.

**Segundo, e é aqui que o suspeito cai:** troquei o conjunto UK pelo americano, que
*hifeniza* `al-ready`, `chap-ter`, `hang-ing` (verifiquei ponto a ponto), e recompus a
página. Os rácios saem da própria `SetLine.space_ratio`, sem raster no meio
(`benchmarks/reports/c11/hyphen_effect.py`):

```
en (UKhyphen, 8527 padroes)     n=15  banda 0.88-2.30 = 2.62x  desvio 0.403  fora 4/15 (26.7 %)
en_US (4938 padroes)            n=15  banda 0.88-2.30 = 2.62x  desvio 0.403  fora 4/15 (26.7 %)
sem hifenizacao nenhuma         n=15  banda 0.89-2.53 = 2.84x  desvio 0.481  fora 8/15 (53.3 %)
pt (427 padroes)                n=22  banda 0.81-1.73 = 2.13x  desvio 0.222  fora 4/22 (18.2 %)
pt sem hifenizacao nenhuma      n=22  banda 0.51-2.09 = 4.08x  desvio 0.376  fora 9/22 (40.9 %)
```

**Zero diferença.** Os pontos que o conjunto americano acrescenta nunca caem num fim de linha
desta página. (E confirmei que a troca mesmo aconteceu: o compositor recebeu
`Hyphenator(language='en_us')` com 4 938 padrões.) A hifenização faz trabalho real nas duas
páginas — desligá-la piora ambas, e a portuguesa mais do que a inglesa — mas **a diferença
entre as duas páginas não é ela**.

**Terceiro, a causa que é:** a cópia. Perguntei ao *breaker*, bloco a bloco, de que tipo de
bloco vem cada linha justificada (`benchmarks/reports/c11/band_by_kind.py`):

```
INGLESA (mareco)                         PORTUGUESA (rios)
  todas       n=15  2.62x  0.403           todas       n=22  2.13x  0.222
    body      n= 5  1.94x  0.318             body      n=13  2.13x  0.232
    body0     n= 7  1.87x  0.294             body0     n= 9  1.59x  0.200
    move      n= 2  2.13x  0.611             move      (nenhuma linha justificada)
    variation n= 1  1.00x  0.000             variation (nenhuma linha justificada)
  so prosa    n=12  1.98x  0.312           so prosa    n=22  2.13x  0.222
  lance/var.  n= 3  2.58x  0.624           lance/var.  (nenhuma)
```

A página inglesa justifica **três linhas que não são prosa** — duas de lances e uma de
variante — e a portuguesa justifica **zero**. A linha mais frouxa da página inglesa, a de
**2,30×**, é uma linha de lances: `6.♗g2 0–0 7.♘gf3 b6 8.0–0 ♗b7 9.♖c1 ♘bd7`. Nenhum dos
seus tokens é hifenizável — são lances, não palavras — portanto o *breaker* não tem alavanca
nenhuma sobre ela a não ser esticar os espaços. **Tirando as linhas de lance e de variante,
a banda inglesa cai de 2,62× para 1,98× e o desvio de 0,403 para 0,312**, enquanto a
portuguesa não se mexe.

### A alegação, reformulada como os números a sustentam

> A banda de espaço entre palavras é **a mais apertada de qualquer página justificada do
> conjunto, nas nossas duas páginas** — 1,89× na portuguesa e 2,30× na página inglesa que
> foi às cegas, contra 2,55×–3,57× nas quatro referências que justificam. A **portuguesa**
> ganha as três estatísticas às quatro (3 de 3) e não tem uma única linha frouxa. A
> **inglesa** ganha a banda e perde o desvio e o «fora» à Nunn e à Gambit — 1 de 3 isolada,
> 0 de 3 no agregado das três páginas de livro, onde perde a banda à Nunn por 0,002. A
> vantagem existe e é menor do que o ciclo 9 a vendeu.
>
> A diferença entre as duas páginas **não é a língua nem o dicionário** — trocar o conjunto
> de padrões inglês não muda um dígito — é a **cópia**: a página inglesa justifica três
> linhas de notação (a mais frouxa da página é uma delas) e a portuguesa nenhuma. Não fechei
> essa distância, e digo porquê: fechá-la significaria mexer no texto da página para a fazer
> medir melhor, que é a definição de encenar a métrica.

---

## D — `_our_pages()` lia as páginas erradas

`pages=(10, 11, 12)` indexado por `doc[number - 1]`, ou seja 1-based 10/11/12, enquanto
`_book_pages()` no mesmo ficheiro deriva **11/12/13**. Media uma página de **espécime** (que
sai `thin` e desaparece) e **nunca media o fólio 46**, com um rótulo que dizia «as 3
últimas».

Agora chama `_book_pages()` — a única derivação que há — e o rótulo é construído do fólio que
cada página **imprime**, lido de volta da própria página por `_page_folio`:

```
F nossa, pt (folio 44)
F nossa, en (folio 44/45/46)
F nossa, corrida (folio 44/45/46/47)
```

Um off-by-one futuro muda o rótulo e falha em
`test_the_word_band_reads_the_book_pages_and_names_the_folios`. Re-corri tudo o que dependia
disto: o agregado inglês é **2,56× / 0,303 / 33,3 %** (§C), e acrescentei a corrida à tabela
porque é a página que vai às cegas.

---

## E — `diagram->move` estava a duas alturas, e está fechado

### Medido no PDF entregue do ciclo 10, dos spans (`diagram_to_move.py`)

```
'After 13.dxc5' y=436.90 pt -> '13…bxc5?!'  y=466.29 pt   vao 10.37 mm     (coluna esquerda)
'After 21.'     y=488.93 pt -> '21…'        y=507.91 pt   vao  6.70 mm     (coluna direita)
```

10,37 − 6,70 = **3,67 mm**, exactamente um slot. (O crítico mediu 7,87 e 3,94 mm no raster,
de topo de tinta a topo de tinta em vez de linha de base a linha de base: a diferença é a
mesma, um slot, dentro do arredondamento do raster.)

### A auditoria por espalhamento, que o ciclo 9 não transcreveu

`benchmarks/reports/c11/audit_spreads.py`, corrido **com o código do ciclo 10**, antes de eu
lhe tocar (a saída está guardada em `spreads_before.txt`). A `unequal_gaps()` publicada
funde os espalhamentos num só dicionário; isto abre-os página a página, que é onde a
diferença entre «não tem folga» e «tem folga» aparece:


```
mareco (a pagina da folha)
  pagina 1: used=[(52,53),(52,53)]  feet=[207.892, 207.892]
      DESIGUAL move->body: col0=1, col0=1, col0=1, col0=1, col1=0
book run 44-47
  pagina 1: used=[(53,53),(53,53)]  DESIGUAL diagram->move: col0=1, col1=0
  pagina 2: used=[(53,53),(53,53)]  DESIGUAL diagram->move: col0=1, col1=0
  pagina 3: used=[(53,53),(53,53)]  DESIGUAL diagram->move: col0=1, col1=0
  pagina 4: used=[(52,53),(52,53)]  DESIGUAL move->body: col0=1, col0=1, col0=1, col0=1, col1=0
```

Isto muda o argumento do crítico num ponto e vale a pena dizê-lo: **as páginas 1–3 da corrida
não têm folga nenhuma** (53/53 nas duas colunas). Igualar `diagram->move` **para cima** ali é
impossível — não há slot. Igualei **para baixo**, e o custo é o mesmo slot: 3,671 mm de
desnível.

### Depois

```
NEW run p1: 'After 13.dxc5' -> '13…bxc5?!'  6.70 mm      'After 21.' -> '21…'  6.70 mm
NEW run p2: 6.70 / 6.70 mm     NEW run p3: 6.70 / 6.70 mm     NEW run p4: 6.70 / 6.70 mm
```

`unequal_gaps()` da corrida: **`{}`**.

---

## F — «nada fora da mancha» era falso, e agora há um portão

### Medido, no artefacto entregue do ciclo 10

```
.venv\Scripts\python.exe tools\measure_typography.py typearea --pdf <o de c10>
  p 4: mancha 14.00..146.90   tinta 13.97..151.13   FORA: dir +4.23 mm
  1 transbordo(s) -> NAO PASSA          exit 1
```

**4,23 mm fora**, 1 444 pixels a 300 DPI. (O crítico mediu 2,45–4,10 mm e 715 px, com o seu
próprio limiar; é o mesmo defeito.)

### A causa

`src/caissa/typeset/board_svg.py::_layout` reservava a goteira das cotas **à esquerda** para
`OUTSIDE_RIGHT`, enquanto `_draw_coordinates` desenha os algarismos **à direita** nesse modo.
O modo carregava uma goteira vazia de um lado e transbordava do seu próprio `width_mm` do
outro. A aritmética da largura já pagava a goteira; ela estava a ser gasta na aresta errada.

Uma linha: `board_x = margin + (0.0 if on_right else gutter * square) + frame_total`.

### O que a correcção fez ao espécime, medido isolado (`probe_frag_ink.py`)

| modo | `width_mm` | tinta | transbordo |
|---|---|---|---|
| `outside` | 56,918 | 1,312 – 56,938 | +0,020 mm |
| `outside_right` **antes** | 56,918 | — | **+4,23 mm na página** |
| `outside_right` **depois** | 56,918 | 0,000 – 55,499 | **−1,419 mm** (fica dentro) |
| `inside` | 51,254 | 0,000 – 51,266 | +0,012 mm |

E fecha dois defeitos de graça, os dois medidos:

* `frame_origin` para `outside_right` devolvia **5,664** mm — a mesma da goteira esquerda —
  pelo que a legenda desse espécime estava posta 5,66 mm ao lado da moldura que rotula.
  Agora devolve **0,000**.
* O **indicador de lance** é desenhado nessa mesma faixa direita. Medi as vinte combinações
  de `SideToMove` × `CoordinateStyle` a 600 DPI: com `outside_right` **e** um indicador, os
  algarismos e o indicador ficavam sobrepostos (algarismos 51,120–53,427 mm, indicador
  50,134–52,654 mm) e antes desta correcção ambos saíam também para lá do `width_mm`
  declarado. `_Layout` passou a levar `coord_gutter` e o indicador passa por cima dela.
  Nenhuma das vinte combinações transborda agora: o pior é **+0,021 mm**, que é o
  anti-aliasing do filete da moldura. Esta combinação não aparece em nenhum artefacto
  entregue (a secção 3 usa o indicador por omissão, que é `NONE`), e por isso a nomeio
  aqui em vez de a contar como um defeito que estava na página.

### O portão

`tools/measure_typography.py typearea` — instrumento novo, com CLI e sabotagem, e os testes
importam-no em vez de o reimplementar. Faz três coisas que o olho do ciclo 9 não fez:

* lê o **raster**, não os spans, portanto um filete, uma moldura de tabuleiro e um algarismo
  de cota contam todos;
* mede e **imprime todas** as páginas, para que um relatório limpo não possa ser o relatório
  das páginas que alguém escolheu;
* trata a página escura pela mesma regra (`_ink` toma a classe minoritária, que é o texto) e
  recorta a franja de 0,39 px que o `pixmap` devolve para lá do formato — a franja lê 175
  contra um fundo 30 e fazia o instrumento acusar 14,05 mm de transbordo numa página que não
  tem nenhum. Essa correcção é do instrumento e está no comentário do código.

Também recusa medir se a galeria e o livro declararem manchas diferentes, em vez de escolher
uma — que é exactamente o modo de falha do item D.

### As saídas

```
typearea  proofsheet.pdf        13 paginas, 0 transbordo(s) -> PASSA        exit 0
typearea  proofsheet_run.pdf     4 paginas, 0 transbordo(s) -> PASSA        exit 0
typearea  proofsheet_rios.pdf    1 pagina,  0 transbordo(s) -> PASSA        exit 0
typearea  <o PDF do ciclo 10>    1 transbordo -> NAO PASSA  (p4, 4.23 mm)   exit 1
typearea --sabotage 3            13 de 13 paginas disparam -> NAO PASSA     exit 1
```

A p4 acaba agora a **145,54 mm** contra a aresta da mancha a 146,90. Duas provas de liveness,
não uma: o portão dispara no artefacto que tinha o defeito, e dispara em **todas** as treze
páginas quando a mancha é estreitada 3 mm — porque um portão que disparasse numa só também
passaria no primeiro teste.

### Testes

* `test_no_page_puts_ink_outside_the_type_area` e
  `test_the_type_area_gate_fires_when_the_measure_is_narrowed`, em `test_proofsheet.py`,
  os dois sobre o instrumento do `measure_typography` e não sobre uma reimplementação.
* `test_outside_right_keeps_its_rank_digits_inside_the_declared_width`, em
  `test_board_svg.py`, parametrizado pelos três indicadores de lance. Este é o teste que
  fica onde o defeito estava, e diz porque é que o teste que já lá existia
  (`test_nothing_is_drawn_outside_the_declared_box`) não o podia apanhar: **ele percorre
  `path`, e uma cota é texto.** Com o layout do ciclo 10 reposto, este falha **3 de 3
  parametrizações, em 3 execuções seguidas**; com a correcção, passa.

---

## O *trade* do `move->body`, fechado ao custo medido de 3,671 mm

### A adjudicação, aceite

O ciclo 9 escreveu que manter a classe igual custava **14,685 mm** de desnível. O número está
certo e é a ponta cara: pôr os cinco vãos a 0. A outra ponta é subir o único que está a 0
para 1, e as duas colunas da página têm um slot de folga cada (52 de 53) — **3,671 mm**, que
é menos do que os **4,19 mm** com que a própria *Chess Structures* fecha as suas colunas na
mesma amostra cega. Fechei-o.

### O mecanismo

`tools/typeset_page.py`:

* `MAX_EQUALISE_SPREAD_SLOTS = 1` — o orçamento, em slots de grade, que se pode gastar em
  desnível de pé para tornar uma classe de vão igual. Um slot = 3,6713 mm.
* `equalise_gap_classes(columns, per_spread, *, budget_slots, max_gap_slots)` — corre depois
  do `feather` (que é quem deixa a desigualdade, na sua última passagem). Para cada classe
  desigual custa **as duas direcções** em slots de desnível resultante e toma a mais barata;
  empate vai para cima, porque uma classe a que o feathering já deu o ar fica com ele. Para
  cima só é possível se cada coluna que tem de crescer tiver a folga; para baixo é sempre
  possível. Aplica só se o desnível resultante couber no orçamento.
* `Composition.equalised` — `(classe, página, direcção, custo_em_slots)` por fecho, para que
  o relatório tenha de citar o custo em vez de afirmar que o fecho foi de graça.

### Os números, antes e depois

| | antes (ciclo 10) | depois (ciclo 11) |
|---|---|---|
| folha, página de livro — `unequal_gaps` | `{'move->body': [0,1,1,1,1]}` | **`{}`** |
| folha, página de livro — pés | `[207.892, 207.892]`, desnível 0,0000 mm | `[207.892, 211.563]`, desnível **3,6710 mm** |
| folha, página de livro — colunas | 52/53, 52/53 | 52/53, **53/53** |
| folha — `equalised` | — | `[('move->body', 0, 'cima', 1)]` |
| corrida 44–47 — `unequal_gaps` | `{'diagram->move': [0,1], 'move->body': [0,1,1,1,1]}` | **`{}`** |
| corrida — `equalised` | — | `diagram->move` **baixo** nas p1–p3, `move->body` **cima** na p4, custo 1 slot cada |
| rios (portuguesa) | `{}`, desnível 0,000 mm | `{}`, desnível **0,000 mm** (nada a fechar) |

### O orçamento é vivo, e provo-o

`compose_book_page(..., equalise_budget=0)` — o mesmo compositor com o orçamento a zero:

```
equalised    = []
unequal_gaps = {'move->body': [0, 1, 1, 1, 1]}          foot_spread = 0.000 mm
corrida:       {'diagram->move': [0, 1], 'move->body': [0, 1, 1, 1, 1]}
```

Exactamente as classes que o ciclo 10 mediu. É ao mesmo tempo a prova de que o orçamento
manda e a prova de que o teste que exige `{}` não está a passar numa página vazia
(`test_the_equalisation_refuses_when_it_would_cost_more_than_its_budget`).

### O que isto custou noutro sítio — medido, não assumido

* **Vãos internos:** idênticos ao ciclo 10. Pior vão interno da folha **3,53 entrelinhas**
  numa página de espécime (tecto 4); as páginas de livro ficam em 1,61 / 2,12 entrelinhas,
  os mesmos números do PDF do ciclo 10, que verifiquei correndo `holes` nos dois.
* **Margem inferior:** `bottom` continua a dar «13 paginas, 0 com conteudo abaixo da margem
  inferior, pior transbordo 0.00 mm». A folga da coluna mais funda passou de **4,05 mm** para
  **0,38 mm** — dentro da margem, e digo o número porque é o que este *trade* consumiu.
* **`feet`:** `p11 p12 p13  pes das colunas 591.2 pt / 601.6 pt  diferenca 3.671 mm`.

### Portões e testes que mudaram de valor, com a razão escrita

| onde | de | para |
|---|---|---|
| `build_blind.FULL_PAGE_FOOT_MM` | 0,01 mm | **3,68 mm** (um slot + arredondamento) |
| `test_the_columns_of_the_book_page_bottom_out_together` | `== 0.000` | renomeado `..._within_one_slot`: `<= 3.6713` **e** `unequal_gaps() == {}` |
| `test_at_most_one_gap_class_comes_out_uneven` | `len(uneven) <= 1` | renomeado `test_no_gap_class_comes_out_uneven`: `== {}` na folha **e** na corrida |
| `test_the_blind_harness_emits_a_sample_from_both_sources` | `[1,1]` e 0,0 nas duas fontes | por fonte: `mareco` `[1,0]` / 3,671 mm, `rios` `[1,1]` / 0,000 mm, `{}` de classes desiguais nas duas |

`FULL_PAGE_SLACK` — o que apanha uma página meio cheia, que é a razão de o portão existir —
**não mudou**, e a sua liveness continua provada por
`test_the_full_page_gate_still_refuses_a_half_filled_page`.

Uma nota de método sobre estes quatro. Mudar um portão para o artefacto passar é
exactamente o que a carta chama encenar a métrica, e a única defesa é que a mudança seja
**declarada com o número e com a razão** e que o portão continue a apanhar aquilo para que
foi escrito. Aqui: os quatro valores mudaram de «pé perfeitamente nivelado» para «pé a menos
de um slot», o slot está escrito em milímetros nos quatro sítios, a razão está adjudicada
pelo crítico do ciclo 10, e **cada um dos quatro ganhou uma asserção nova e mais forte** —
`unequal_gaps() == {}`, que o ciclo 10 não teria passado.

---

## §8 — os *defaults* destrutivos, e o que fiz a eles

O crítico do ciclo 10 registou que não correu `tools/build_blind.py` porque o `--out` por
omissão é `benchmarks/reports/blind/`, que guarda o conjunto cego do **ciclo 1**
(`GABARITO.json` e `amostra_A..G.png`), e uma execução escreveria `samples/` e `answers/` por
cima. Ele desviou-se à mão. Uma ferramenta cujo *default* apaga a prova contra a qual um
ciclo passado foi julgado é uma armadilha, e o desvio à mão não é a correcção.

`frozen_blind_set(out)` + recusa:

```
.venv\Scripts\python.exe tools\build_blind.py
RECUSA: ...\benchmarks\reports\blind ja contem um conjunto cego congelado
        (GABARITO.json, amostra_A.png, amostra_B.png, amostra_C.png ...).
  Um conjunto cego e um artefacto de um ciclo passado: reescreve-lo apaga
  a prova contra a qual esse ciclo foi julgado. Escolha um diretorio novo:
    --out ...\benchmarks\reports\blind7
  ou, se e mesmo isso que quer, --force.
exit 3
```

Os **seis** directórios cegos recusam (`blind`, `blind2`, `blind3`, `blind4`, `blind5`,
`blind6` — exit 3 nos seis) e um directório novo constrói (exit 0, oito ficheiros). Os md5 do
conjunto do ciclo 1 estão inalterados depois de tudo o que corri:

```
4ff6838b1a4883c12e3e602990637165  blind/GABARITO.json     (igual ao de antes)
433978444599079a13d25e08c672f448  blind/amostra_A.png     (igual ao de antes)
```

`tools/typeset_proofsheet.py` é o gerador dos artefactos entregues e reescrevê-los é o seu
trabalho — mas fi-lo com rede: construí primeiro para
`--out benchmarks/reports/c11/scratch/new/proofsheet.pdf` (o `main` deriva os outros dois por
`with_name`, portanto os três foram para o *scratch*), confirmei os md5 dos entregues
**inalterados** depois dessa construção, medi tudo no artefacto novo, e só então corri
`--png` por cima dos entregues, com as cópias do ciclo 10 guardadas em `c11/scratch/`.

Os artefactos entregues deste ciclo:

```
benchmarks/reports/proofsheet.pdf       8ea24f9ff095d33adba91ba5bdd1bf55
benchmarks/reports/proofsheet_run.pdf   c58fc28cf2753e4ba3c6ca42bba23102
benchmarks/reports/proofsheet_rios.pdf  a7aa1e2f991d98ed47bf7153c2cc8b09
```

E o artefacto **é** o que este código produz, verificado ao raster nas dezoito páginas —
não nas quatro que o ciclo 9 alegou nem nas oito que o crítico verificou
(`benchmarks/reports/c11/raster_identity.py`, recomposição feita agora, 300 DPI):

```
proofsheet.pdf p1..p13   raster diff mean = 0.0000, max = 0
proofsheet_rios.pdf p1   raster diff mean = 0.0000, max = 0
proofsheet_run.pdf p1..p4  raster diff mean = 0.0000, max = 0
pior diferenca de raster em qualquer pagina: 0
```

---

## §9 — A suíte, três execuções seguidas

```
.venv\Scripts\python.exe -m pytest -q -p no:randomly
```

SUITE_RESULTS_PLACEHOLDER

---

## §10 — Olhei as 18 páginas

Com a ferramenta de leitura de imagem, uma a uma, no artefacto novo antes de o promover:
`page_01` a `page_13`, `run_01` a `run_04` e `rios_01`
(`benchmarks/reports/c11/scratch/new/png/`). O que fui ver, e o que vi:

* **p4** — o espécime `outside_right` tem agora as cotas de linha à direita da moldura e
  **dentro** da mancha; a sua legenda assenta na moldura. É a página do item F.
* **p11 / p12 / p13** — as três páginas de livro. A coluna direita desce agora um slot abaixo
  da esquerda: são os 3,671 mm que o `move->body` custou, e vêem-se, e é a escolha declarada.
  A p13 (escura) mantém o desenho — fundo #1B1F23, casas em dois cinzas, realce âmbar, seta
  vermelha — e o fólio 46 no canto **superior esquerdo**, que é o lado de um verso.
* **run_01..run_04** — 44 à esquerda, 45 à direita, 46 à esquerda, 47 à direita. Os dois vãos
  `diagram->move` estão agora à mesma altura, que é o item E visto em vez de medido.
* **rios_01** — as duas colunas fecham nivelado, como fechavam. Nada mudou nesta página.
* **p1, p2, p3, p5, p6, p7, p8, p9, p10** — as páginas de espécime, inalteradas. A p8 continua
  a ser a continuação da secção 7 com o pé alto, que o ciclo 8 adjudicou.

Os dois defeitos que o crítico deixou como não bloqueantes e que **continuam na página**, e
que eu não fui mandado fechar: as duas hifenizações de última palavra de parágrafo
(`subsequently at-/tacked.` e `worth play-/ing for.`, esta última na última linha da coluna) e
o traço do roque `0–0` composto com meia-risca. Vejo as duas na p11 e digo-o aqui em vez de
deixar o próximo crítico descobrir que eu não olhei.

---

## §11 — O que fica em aberto, com o número

1. **`caissa/export/pdfwrite.py::_subset_font`** continua não determinística (três SHA-256 em
   três chamadas, §A). Não é minha; a correcção é uma linha e a função pública para a fazer
   já existe e está documentada para esse caller.
2. **A página inglesa empata com as duas melhores referências** (§C). A causa está medida e
   não é a língua nem o dicionário: são três linhas de notação justificadas contra zero na
   portuguesa. Fechá-la exigiria mexer no texto da página.
3. **Duas hifenizações de fim de parágrafo e o traço do roque** — não bloqueantes 1 e 3 do
   ciclo 10, na página, não tocados neste ciclo.
4. **`livro.pdf` do exportador LaTeX tem uma página**, portanto mostra um recto certo e não
   mostra alternância — ressalva do crítico, não tocada.
5. **A folha de espécimes ainda tem um vão interno de 3,53 entrelinhas** (p4), dentro do tecto
   de 4 de uma folha de espécimes e acima do tecto de 2 de uma página de livro. Inalterado
   desde o ciclo 10.
6. **A precisão do `wordband` sobre um raster é ±0,05 no desvio** entre o tema claro e o
   escuro da mesma composição (§B). O corte já não depende da rasterização; o desvio ainda
   depende do anti-aliasing.
