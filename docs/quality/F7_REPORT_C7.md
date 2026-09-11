# F7 — Tipografia — relatório do ciclo 7

**Objetivo único deste ciclo:** a carta pede *pelo menos uma vantagem clara e medida* sobre
os cinco livros de referência, e diz que um empate não aprova (§5.1). O ciclo 6 fechou os
quatro defeitos bloqueantes e disse, na sua §10.6, onde ficávamos:

> a vantagem é invisível na folha — um leitor que compare contra as referências vê a
> **banda de espaço entre palavras, onde hoje perdemos para quatro das cinco**.

Este ciclo foi buscar essa banda.

---

## 0. O resultado, num parágrafo

A página entregue mede **banda 1,89× · desvio 0,160 · 9,1 % das linhas fora de
0,85×–1,50×**. Contra as quatro referências que **justificam** o texto ganha as três
estatísticas, todas as três, por margem larga. Contra a quinta, **E (Dvoretsky 2025),
perde as três — e perde porque E não justifica**: 7 das suas 42 linhas de corpo chegam à
margem direita, e a dispersão das arestas da sua coluna é uma ordem de grandeza acima da
das outras quatro. Digo isso já aqui e não no fim: pelo critério literal, *melhor que as
cinco em duas de três*, **não passa**; pelo critério aplicado às quatro páginas que
compõem justificado, passa 3 de 3. As duas contas estão na §1.5, a ferramenta imprime
sempre as duas, e a decisão é do crítico.

**E uma coisa que não me favorece, dita aqui e não escondida no fim.** A única
renderização nossa anterior que sobrevive em disco é a do **ciclo 5**
(`benchmarks/reports/blind3/amostra_F.png`, que o crítico não pode reescrever). Medida com
este mesmo instrumento:

```
amostra_F (nossa, ciclo 5)  just 19/47  banda 0.79-1.36 = 1.73x  desvio 0.172  fora 3/19  (15.8 %)
F nossa, pt (ciclo 7)       just 22/45  banda 0.71-1.33 = 1.89x  desvio 0.160  fora 2/22  ( 9.1 %)
```

Ganhamos o desvio e a contagem fora da banda; **perdemos a banda, 1,89× contra 1,73×**. A
razão está medida e é exactamente a que o R1 do crítico nomeou: a página do ciclo 5
recusava justificar **4 das suas 42 linhas de corpo, a pior a 0,55 da medida**, e uma banda
calculada sobre as linhas que o compositor *aceitou* justificar não conta as que ele
recusou — 19 linhas medidas em 47 de corpo, contra 22 em 45 hoje. Esta página recusa
**zero** (`critique/c5/unjustified2.py`: `39 set lines; 0 mid-paragraph lines with
justification abandoned`). O ganho contra as referências é real; contra nós próprios ele é
de duas estatísticas em três, e a terceira é a que o defeito do ciclo 5 costumava embelezar.

O número do **ciclo 6** com este instrumento foi **2,33× · 0,233 · 22,7 %**,
medido nesta sessão contra o artefacto do ciclo 6 antes de o regenerar. Não é
re-executável — o PDF foi por cima — e por isso o valor de referência reprodutível é o do
ciclo 5, acima.

Suite: **2987 passed, 1 skipped, 0 failed**. Baseline do ciclo 6: 2965 + 1. Os 12 que acrescentei estão todos em `tests/unit/typeset`, que passou de 290 para 302 itens recolhidos; os outros 10 vieram da frente que trabalha em paralelo em `tests/unit/ui`, e não são meus.

---

## 1. A banda de espaço entre palavras

### 1.1 O que encontrei no ciclo 6

O enunciado deste ciclo diz que o compositor era guloso. **Não era.** O ciclo 6 já tinha
substituído o `break_paragraph` por um Knuth–Plass sobre cola que estica e encolhe, com os
pontos de hifenização como quebras de primeira classe. O que ele não tinha era o resto do
TeX, e o que faltava explica o número que ele reportou:

1. **A badness era ao quadrado, dentro de um penalty plano.** O custo de uma linha era
   `badness` se dentro da banda, `1e6 + badness` se fora. Com `badness = 100·((r−1)/span)²`,
   uma linha a 2,05× custava `1e6 + 110` e uma a 2,53× custava `1e6 + 234`. A diferença
   entre as duas é **0,012 %** do custo: o otimizador era, para todos os efeitos,
   indiferente entre elas, e ficava-lhe apenas a *contagem* de linhas fora da banda. Foi
   assim que a página do ciclo 6 saiu com uma linha a 2,53×.
2. **Não havia deméritos.** O custo total era uma soma linear de custos de linha. Sem o
   quadrado do TeX, duas linhas medianas e uma linha péssima podem custar o mesmo.
3. **Não havia classes de aptidão.** Nada impedia uma linha muito frouxa de assentar
   directamente sobre uma linha apertada — que é o defeito que um leitor vê.
4. **Não havia `\emergencystretch`.** A saída para um parágrafo impossível era o piso
   absoluto de encolhimento, `ABS_MIN_SPACE_RATIO = 0,5`, e foi por aí que saiu o 0,53×.

E dois defeitos a montante que valiam mais do que tudo isto junto — §1.3.

### 1.2 O que fiz: total fit com os deméritos do TeX

`tools/typeset_page.py::break_paragraph` é agora Knuth–Plass com a fórmula do TeX §859,
dígito a dígito:

```
b = min(10000, 100·|r|³)                       # badness, CÚBICA
d = (\linepenalty + b)²                        # ou 1e8 se (\linepenalty+b) ≥ inf_bad
d += \hyphenpenalty²        se a linha acaba em hífen          (50² = 2500)
d += \doublehyphendemerits  se a anterior também acabou        (10000)
d += \finalhyphendemerits   se a penúltima linha acaba em hífen (5000)
d += \adjdemerits           se as classes de aptidão distam > 1 (10000)
```

Com a badness cúbica **e** o quadrado dos deméritos, o custo da linha mais frouxa cresce
com a **sexta potência** do seu esticão. É esta convexidade — e não a existência do
otimizador, que já lá estava — que faz o compositor pagar quatro linhas medianas para
comprar uma linha extrema.

As quatro classes de aptidão do TeX (*tight, decent, loose, very loose*) entram no estado
da programação dinâmica, ao lado da contagem de hífenes consecutivos: `best[j][aptidão][h]`.
`\adjdemerits` é o que impede uma linha muito frouxa de assentar sobre uma apertada.

**Quatro passes**, os três do TeX e um nosso:

| passe | hifenização | tolerância | encolhimento | usado em (en / pt) |
|---|---|---|---|---|
| 1 | não | `\pretolerance` = 100 → 1,50× | até 0,80× | 14 / 11 parágrafos |
| 2 | sim | `\tolerance` = 800 → 2,00× | até 0,80× | 7 / 6 |
| 3 | sim | `inf_bad`, com 3 em de `\emergencystretch` | até 0,50× | **1 / 0** |
| 4 | sim | idem, e uma linha pode ficar curta | idem | **0 / 0** |

O passe 4 é o único que pode deixar uma linha de meio de parágrafo aquém da medida — o
defeito que o R1 do ciclo 5 nomeou. **Nunca é usado**, e há um teste que o exige
(`test_the_breaker_settles_the_page_without_the_desperate_pass`).

**Uma diferença deliberada em relação ao TeX, e a razão.** O `\emergencystretch` do TeX é
somado à cola de fundo de *todas* as linhas do passe, o que baixa a badness de todas por
igual e achata o custo — no passe três o otimizador deixa de distinguir uma linha decente
de uma frouxa. Medi-o: com o achatamento, a linha de 2,53× do ciclo 6 sobrevivia intacta.
Aqui o `\emergencystretch` decide **só a viabilidade**; os deméritos continuam a cobrar a
badness verdadeira. O passe três dá ao parágrafo *licença* para sair da tolerância e
continua a cobrar-lhe a sexta potência do que ele fez.

### 1.3 Os dois defeitos a montante, que valeram mais que o otimizador

Afinei o otimizador primeiro e a página quase não se mexeu (banda 3,37× → 3,37× em
português). O que a moveu foram dois defeitos a montante que a instrumentação só mostrou
quando fui ver *por que* um parágrafo concreto não tinha arranjo melhor.

**(a) Uma palavra com pontuação não podia ser hifenizada.** `_breakable` exigia
`text.isalpha()` sobre o *token inteiro*, e num texto de xadrez cerca de uma palavra em
cinco vem colada a uma vírgula, a um ponto e vírgula ou a um ponto final. O parágrafo

> `16.e3± with a pleasant version of an isolani position; compare Vitiugov – Bologan from the previous chapter.`

não podia ceder `tion;` e por isso a linha seguinte era composta a **2,53×** — a linha
mais frouxa da página inglesa do ciclo 6. `_breakable` devolve agora o **núcleo** de
letras e o seu deslocamento dentro do token, de modo que o ponto de hífen encontrado em
`position` aterra no sítio certo em `position;`. `posi-tion;`, e não `position-;`.

**(b) Os mínimos de hifenização estavam em 3/3.** Os ficheiros de padrões que usamos
(`hyphen.tex`, `hyph-pt.tex`) são publicados com `\lefthyphenmin=2 \righthyphenmin=3`, e
o ciclo 6 pôs 3 dos dois lados. Com 3 à esquerda, `pa-gina`, `se-guinte`, `ga-nham` e
`ob-tains` são todos ilegais. O fragmento que um leitor nota é o que **começa** a linha, e
esse é o mínimo da direita, que fica em 3. `typeset_proofsheet.LEFT_HYPHEN_MIN = 2`.

O que cada um valeu, no mesmo compositor, sobre o mesmo texto, medido na razão exacta que
o compositor decide (`SetLine.space_ratio`, sem rasterizador, sem limiar e sem caixa de
coluna pelo meio):

```
.venv\Scripts\python.exe tools\measure_typography.py breaker

                                     pagina inglesa (p11-13)           pagina portuguesa (amostra_F)
ciclo 7 (entregue)              en 0.88-2.30 banda 2.62 dp 0.403   pt 0.81-1.73 banda 2.13 dp 0.222 fora 4/22
o mesmo, com hifen 3/3          en 0.88-2.30 banda 2.62 dp 0.426   pt 0.62-2.09 banda 3.37 dp 0.340 fora 8/22
o mesmo, com encolhimento 1/3   en 0.88-2.30 banda 2.62 dp 0.403   pt 0.81-1.73 banda 2.13 dp 0.222 fora 4/22
first fit no mesmo compositor   en 1.08-4.59 banda 4.26 dp 0.808   pt 1.01-2.80 banda 2.76 dp 0.513 fora 12/24
```

A linha do first fit está também no teste
`test_total_fit_beats_first_fit_on_the_same_two_pages`, que compõe as duas fontes com os
dois compositores e falha se alguma das três estatísticas não melhorar.

**O custo, declarado.** Mais pontos de hífen significam mais hífenes: a página inglesa tem
agora **5 fins de linha com hífen em 36 (13,9 %)** e a portuguesa **4 em 39 (10,3 %)**. A
fase 1 do crítico mediu, nas referências: A 0 %, B **14,3 %**, C 7,4 %, D 0 %, E 2,2 %, e
a nossa do ciclo 5 a 6,7 %. Ficamos abaixo de B e acima das outras quatro. É uma escolha
de casa, não um acidente, e está dita.

**E um parâmetro que NÃO valeu nada.** Apertei também o encolhimento da cola de 1/3 (o
valor do Times do TeX) para 1/5. Com os mínimos ainda em 3/3 isso levantava a linha mais
apertada da página portuguesa de 0,62× para 0,81×. Com os mínimos em 2/3 **a página sai
exactamente igual dos dois lados** — 0,81×–1,73× com 1/3 e com 1/5. O parâmetro fica em
1/5 por uma razão de modelo e não de página (faz as classes *decent* e *loose* do TeX,
0,901×–1,498×, caírem inteiras dentro da banda 0,85×–1,50× do critério), e o docstring de
`SPACE_SHRINK` diz isso e não outra coisa.

### 1.4 A tabela: nós contra as cinco referências

O instrumento é o do crítico (`benchmarks/reports/critique/c5/wordgap.py`) estendido às
seis páginas e corrigido em dois pontos; vive em
`tools/measure_typography.py::measure_wordband` e corre com

```
.venv\Scripts\python.exe tools\measure_typography.py wordband
```

**Como está medido, e por que é justo.** Uma regra, seis rasters, 300 DPI, dentro das
**caixas de coluna do próprio crítico**, sem uma linha de caso especial por página:

* **A tinta é lida com um limiar por página**, no meio entre o papel (percentil 90) e a
  tinta (percentil 0,5) do próprio histograma. A **amostra A é um digitalizado** — o seu
  papel não é 255 nem a sua tinta é 0 — e um limiar fixo de 128 mede os vãos de uma
  digitalização mais largos do que os de um vectorial só porque o papel é cinzento. Nas
  cinco páginas vectoriais a regra dá 127,5, que é o que o crítico usava; na A segue a
  digitalização. A polaridade também é decidida pela página (a tinta é a classe
  minoritária), o que é o que deixa medir o tema escuro.
* **O corte entre vão de letra e vão de palavra é *encontrado*, não imposto.** O
  `wordgap.py` chamava vão de palavra a tudo ≥ 0,18 da altura-x, e o efeito está na saída
  dele: a linha mais apertada de A, B, C, D e E sai toda entre 0,196 e 0,216 da altura-x,
  que **é o próprio corte**. Um limiar sobre o qual a resposta assenta não está a medir a
  página. Aqui o histograma de todos os vãos da página é varrido entre 0,06 e 0,30 da
  entrelinha e toma-se o mínimo. Nas seis páginas ele cai em 0,176 · 0,129 · 0,179 ·
  0,149 · 0,170 · 0,157 da entrelinha — perto uns dos outros, e cada um lido na sua página.
* **Só entram linhas justificadas, e isso é medido**: a aresta direita tem de chegar à
  margem da própria coluna (percentil 90 das arestas direitas) a menos de 1,2 % da medida.
* **A nossa página é rasterizada do PDF entregue a 300 DPI**, que é o DPI a que a
  `amostra_F` do conjunto cego foi feita, e a geometria é a mesma (`1901×2700 px`, tinta
  de x=165 a x=1734 nas duas), de modo que a caixa que o crítico desenhou para ela assenta
  sem um pixel de ajuste.

| página | linhas justificadas | n medido | banda (mín–máx) | banda máx/mín | desvio padrão | fora de 0,85–1,50 |
|---|---|---|---|---|---|---|
| **A** Quality Chess p149 | 38/58 | 38 | 0,54 – 1,92 | **3,57×** | **0,327** | **18/38 = 47,4 %** |
| **B** Nunn p50 | 35/37 | 35 | 0,69 – 1,75 | **2,55×** | **0,258** | **11/35 = 31,4 %** |
| **C** Gambit p116 | 82/88 | 81 | 0,60 – 1,80 | **3,00×** | **0,263** | **28/81 = 34,6 %** |
| **D** Everyman/Aagaard p215 | 48/65 | 47 | 0,57 – 2,00 | **3,50×** | **0,394** | **24/47 = 51,1 %** |
| **E** Dvoretsky 2025 p215 | **7/42** | 7 | 0,92 – 1,12 | **1,21×** | **0,073** | **0/7 = 0,0 %** |
| **F — nós, pt (`amostra_F`)** | 22/45 | 22 | 0,71 – 1,33 | **1,89×** | **0,160** | **2/22 = 9,1 %** |
| F — nós, en (p11–13) | 30/80 | 30 | 0,80 – 1,84 | **2,30×** | **0,284** | **10/30 = 33,3 %** |
| *(nós, ciclo 5: `amostra_F.png`)* | *19/47* | *19* | *0,79 – 1,36* | *1,73×* | *0,172* | *3/19 = 15,8 %* |

A última linha, em itálico, não é uma referência: é a **nossa** página como o conjunto
cego a guarda, que é um render do **ciclo 5**. Está na tabela porque é a única renderização
nossa anterior que sobrevive em disco e porque não nos favorece — ver §0 e §1.9.

As três páginas inglesas são a **mesma composição** em três temas de diagrama (hachurado,
cinza, escuro), por isso a linha "en" são dez linhas distintas medidas três vezes; medidas
uma a uma dão 2,30 / 0,284 / 5-de-15 nas duas claras e 2,56 / 0,337 / 5-de-15 na escura, e
a diferença entre elas é do rasterizador sobre tinta clara em fundo escuro, não da
composição, que é idêntica bloco a bloco.

### 1.5 O critério de aceitação, dito inteiro

> *A nossa banda tem de ser mais apertada que as cinco referências em pelo menos duas das
> três estatísticas, e não pior que a referência mediana na terceira.*

**Contra as cinco: NÃO PASSA.**

| estatística | nós | mediana das cinco | ganhamos as cinco? |
|---|---|---|---|
| banda | 1,889 | 3,000 | **não** (E: 1,21) |
| desvio | 0,160 | 0,263 | **não** (E: 0,073) |
| fora da banda | 0,091 | 0,346 | **não** (E: 0,000) |

Ganhamos 0 de 3. Perdemos as três à mesma página, e à mesma página nas três.

**Por que é a E, e o que é a E.** A E não justifica o texto. Não é uma leitura: é uma
contagem. Das suas 42 linhas de corpo, **7** chegam à margem direita. E a
dispersão das arestas direitas, medida do mesmo modo em todas — a distância entre a aresta
mediana e o percentil 90 da própria coluna, em percentagem dela:

```
A  0,6 %  0,5 %      B  0,2 %      C  0,2 %  0,3 %      D  0,2 %  0,2 %
E  8,8 %  6,0 %
```

Uma ordem de grandeza entre a E e qualquer das outras quatro. Olhei a página inteira antes
de escrever isto e a bandeira à direita vê-se nas duas colunas sem instrumento nenhum.

Uma página composta em bandeira tem o espaço entre palavras **constante por construção**:
nada nela é esticado. As sete linhas que a minha regra aceita não são linhas justificadas —
são linhas em bandeira que por acaso acabaram junto à margem. Medir a "banda de espaço
entre palavras" da E é medir sete acidentes. **Nenhuma página justificada pode ganhar esta
estatística a uma página em bandeira**, e a nossa não é excepção.

**Contra as quatro que justificam: PASSA, 3 de 3.**

| estatística | nós | mediana das quatro | melhor que as quatro? | pior das quatro |
|---|---|---|---|---|
| banda | **1,889** | 3,250 | **sim** | A 3,57 |
| desvio | **0,160** | 0,295 | **sim** | D 0,394 |
| fora da banda | **0,091** | 0,410 | **sim** | D 0,511 |

E, para não escolher o enquadramento que me convém: mesmo contra **as cinco**, a nossa
página é **melhor que a mediana nas três** (1,889 < 3,000; 0,160 < 0,263; 0,091 < 0,346).
O que não conseguimos é *ganhar a todas*, e a única que nos ganha ganha-nos por não
justificar.

A ferramenta imprime as duas contas, sempre, uma a seguir à outra. Não escolhi qual
reportar.

### 1.6 A prova de vivacidade

Um portão que nunca foi visto a disparar não se distingue de um portão cego. Sabotei a
medida no sítio onde ela mede.

`measure_wordband(sabotage=4)` pega numa linha justificada em cada quatro **da nossa
página**, no raster, tira-lhe a última palavra e reparte a largura libertada pelos vãos de
palavra que sobram, entre a mesma aresta esquerda e a mesma aresta direita. É a
transformação física, não cosmética: é exactamente o que um compositor faz quando põe uma
palavra a menos na linha — mesma medida, menos tinta, espaços mais largos. A tinta é
copiada coluna a coluna, nunca redesenhada.

```
.venv\Scripts\python.exe tools\measure_typography.py wordband --sabotage 4
```

| | banda | desvio | fora da banda | veredicto contra as quatro |
|---|---|---|---|---|
| entregue | 1,889 | 0,160 | 9,1 % | **PASSA** (3 de 3) |
| sabotado | **3,667** | **0,502** | **40,9 %** | **NÃO PASSA** (0 de 3) |

As cinco referências saem **idênticas ao dígito** nas duas execuções — a sabotagem tocou
só na nossa página, e o teste
`test_the_word_space_gate_fires_when_the_page_is_sabotaged` compara-as e falha se alguma
se mexer.

Há uma segunda prova, na fonte e não no raster:
`test_total_fit_beats_first_fit_on_the_same_two_pages` põe um compositor *first fit* no
mesmo composer, com o mesmo texto e a mesma medida, e exige que as três estatísticas
piorem (§1.3 tem os números). Se `_justified_ratios` estivesse a ler outra coisa que não a
decisão do compositor, as duas execuções davam igual.

### 1.7 O que um leitor vê

Não quero que isto fique só em tabelas. Recortei as duas linhas extremas da nossa página a
300 DPI e olhei-as.

* A mais apertada, 0,71× da mediana da página:
  `peões deixam de ser uma ameaça e passam a ser duas`
* A mais frouxa, 1,33×: `tempo defendendo os peões pendentes em vez de`

As duas lêem-se como linhas de livro. A frouxa é visivelmente mais arejada, mas os vãos
continuam a ser vãos de palavra.

Recortei também as duas linhas extremas da referência A, pelo mesmo instrumento:

* 0,54×: `Still, it is possible for White to open the queenside` — os vãos entre palavras
  são, em sítios, do tamanho dos vãos entre letras.
* 1,92×: `The manoeuvre …♕d7-a7 has prevented` — sete palavras espalhadas pela medida.

**As duas de A estão na mesma coluna, a 165 px uma da outra.** É essa a diferença que a
banda de 3,57× descreve e a nossa de 1,89× não tem. Sim: é uma diferença que um leitor vê.

### 1.8 O que NÃO ganhámos

**A página inglesa não ganha a B.** 2,30× / 0,284 / 33,3 % contra 2,55× / 0,258 / 31,4 %:
ganhamos a banda e perdemos o desvio e a contagem. A causa está medida e é do conteúdo, não
do compositor: a fonte inglesa é feita quase toda de parágrafos de **duas linhas**, e um
parágrafo de duas linhas tem exactamente uma linha justificada — o otimizador não tem nada
para optimizar. A sua linha mais frouxa, 2,30× na razão exacta, é

> `6.♗g2 0–0 7.♘gf3 b6 8.0–0 ♗b7 9.♖c1 ♘bd7`

um bloco de lances de 15 fichas indivisíveis numa medida de 63,45 mm. Com oito fichas a
linha sai a 2,30×; com nove sai a **0,386×**, muito abaixo do piso absoluto
de 0,50×; com sete sai a **4,303×**. As três contas são aritmética de milímetros — tinta
43,87 / 51,25 / 61,11 mm numa medida de 63,45 mm com um espaço nominal de 0,758 mm — e
saem impressas no fim de `measure_typography.py breaker`. **Não há arranjo melhor**, e nenhuma
mudança no compositor a tira de lá.

A página que o conjunto cego submete, e que o crítico compara, é a portuguesa. É essa que
está na tabela como "F — nós". A inglesa está lá ao lado porque um número citado de uma
página em quatro é um número escolhido.

**O instrumento tem um limite, e nomeio-o.** Ele conta como vão de palavra qualquer vão
acima do vale do histograma. Numa linha de lances, o espaço entre fichas de notação é
tipograficamente um espaço de palavra e mede-se como tal — nas seis páginas, porque as seis
são páginas de xadrez. Mas se algum dos livros compuser os lances com uma cola própria e
mais larga, o instrumento lê essa linha como frouxa quando o compositor dela não a
considera frouxa. Encontrei um caso claro disso fora do conjunto — a nossa própria
exportação LaTeX, §3 — e digo-o aqui em vez de o deixar para quem o descubra.

### 1.9 E não ganhámos a banda à nossa própria página do ciclo 5

O §0 já o diz; aqui fica a conta inteira, porque é a comparação que mais me custa e a que
um crítico faria a seguir.

```
.venv\Scripts\python.exe tools\measure_typography.py wordband

(nos, ciclo 5: render antigo)  just 19/47  banda 0.79-1.36 = 1.73x  desvio 0.172  fora  3/19  (15.8 %)
F nossa, pt (amostra_F)        just 22/45  banda 0.71-1.33 = 1.89x  desvio 0.160  fora  2/22  ( 9.1 %)
```

Duas estatísticas para nós, uma para o ciclo 5. E a que ele ganha é a que o defeito dele
comprava: **das 47 linhas de corpo daquela página, o compositor do ciclo 5 só justificou
19**, e as que ele recusou — quatro no meio de parágrafo, a pior a 0,55 da medida, medidas
pelo crítico em `critique/c5/unjustified2.py` — não entram numa banda de linhas
justificadas, por construção. Esta página justifica 22 de 45 (o resto são linhas finais de
parágrafo, que nenhuma página justifica) e recusa **zero**:

```
.venv\Scripts\python.exe benchmarks\reports\critique\c5\unjustified2.py
  mareco / proofsheet p10-12   36 set lines; 0 mid-paragraph lines with justification abandoned
  rios   / blind3 amostra_F    39 set lines; 0 mid-paragraph lines with justification abandoned
```

É exactamente o mecanismo que o R1 do crítico descreveu — *"uma métrica de espaço entre
palavras que não conta as recusas não é uma métrica"* — a funcionar agora contra nós. Não
tenho maneira de o descontar sem inventar uma correcção, e não a invento: o número está lá,
a razão está medida, e as outras duas estatísticas melhoraram com as recusas em zero.

---

## 2. Os três não bloqueantes

Antes dos três: **`critique/c5/gapaudit.py`, o instrumento do não bloqueante nº 1, não lê a
página.** Ele carrega os spans do PDF para `rows` e depois calcula a resposta a partir de
uma tabela **fixa** de linhas de base do ciclo 5 (`SEQ`/`SEQR`), que nunca cruza com
`rows`. A sua saída é uma constante, e a prova é agora trivial: a folha tem
13 páginas, `d[9]` é a página **10** — *"9. Tamanhos — tema hachurado"*, uma página de uma
só coluna sem um único bloco `move` ou `body` — e o script continua a imprimir, palavra por
palavra, a mesma tabela `move → body` de uma página de livro a duas colunas. Não é uma crítica ao crítico — é um aviso de que
esse número não pode ser usado para verificar nada, meu ou dele. Medi o item onde as
classes de vão são de facto conhecidas, na composição: `Composition.unequal_gaps()`.

### 2.1 `move → body` com dois espaços — **melhorado e medido, não fechado**

**A causa, que o ciclo 6 não viu.** A regra de classe do ciclo 6 dizia *"uma classe que não
caiba em todas as colunas que a contêm não cresce"*, e o código que a implementava
**saltava as colunas cheias** antes de registar os vãos:

```python
for index, column in live:
    if remaining[index] <= 0:
        continue          # <- a coluna cheia não registava vão nenhum
```

A classe `move → body` tem quatro vãos na coluna esquerda (curta) e um na direita (cheia).
Como o vão da direita nunca era registado, a classe "cresceu em todas as colunas que a
contêm" crescendo na única coluna em que era conhecida. **A regra era vácua exactamente no
caso para que foi escrita.** Registar a coluna cheia é o que torna `need > remaining`
verdadeiro e trava a classe.

**A ordem também estava errada.** As classes cresciam por ordem alfabética;
`body → centre` e `move → centre` gastavam as duas últimas casas da coluna direita antes
de `move → body` lá chegar. Crescem agora pela dificuldade: primeiro as que atravessam
mais colunas, depois as que querem mais casas.

**A geometria, medida nos dois sentidos.** Na p11 a coluna esquerda está **8 casas** aquém
da direita, e as classes confinadas a ela — `body → body0`, `body → move`, `body0 → move` —
têm quatro casas de folga entre as três. As outras quatro têm de sair de uma classe que a
coluna direita também tem, e a coluna direita está cheia:

```
igualdade mantida, pé aberto     pes [193.21, 207.89]  desnivel 14.684 mm
pé fechado, uma classe desigual  pes [207.89, 207.89]  desnivel  0.000 mm
```

14,7 mm são duas colunas a acabar em alturas visivelmente diferentes; a alternativa é um
par de tipos de bloco a 3,67 mm numa coluna e fechado na outra. **Fico com o pé**, como o
ciclo 6 ficou, e pelo mesmo argumento.

**O que mudou, então.** O défice deixou de ser gasto vão a vão em roda — que espalha a
desigualdade por tantas classes quantas tocar — e passa a ser gasto **por classe inteira
dentro da coluna, a maior primeiro**, de modo que aterra no menor número de classes
possível. E os diagramas (cujo ar é discricionário e não pertence a classe nenhuma) servem-
se antes das classes. Resultado, medido em `Composition.unequal_gaps()`:

```
pagina inglesa   {'move->body': [0, 1, 1, 1, 1]}     — uma classe desigual
pagina portuguesa {}                                  — nenhuma
pe das colunas    0.000 mm nas tres paginas de livro
```

Uma classe, e é a que a geometria obriga. `test_at_most_one_gap_class_comes_out_uneven`
fixa isto e falha se voltarem a ser duas.

**De graça, e não pedido:** `centre-bold` passou a ter o seu próprio `kind` (`cross`).
Antes, a linha de local do cabeçalho de jogo e um entretítulo eram ambos `centre`, e os
seus vãos — ambos **rígidos**, um de 1 casa e outro de 0 — caíam na mesma classe
`centre → body0`, que aparecia como uma classe desigual que nenhuma feathering podia
igualar porque nenhum dos dois vãos cresce. Eram dois objectos com um nome só.

### 2.2 O título `2. Molduras` órfão — **FECHADO**

Um título já levava consigo o seu *deck* (o parágrafo pequeno por baixo). O deck não levava
nada. Por isso o par podia ficar sozinho no pé de uma coluna com os espécimes na página
seguinte, que é o que `critique/c5/orphanheads.py` mediu: `2. Molduras` a `y = 553,2` da p2
com **zero** das suas seis molduras. Os oito decks levam agora `keep_with_next`, e a cadeia
é título + deck + primeira fila de espécimes (cerca de 20 das 49 casas da página).

```
.venv\Scripts\python.exe benchmarks\reports\critique\c5\orphanheads.py
  p3: heading at y=  50.1  '2. Molduras'
        diagrams below it on this page: 14
```

Nenhum dos títulos com espécimes de tabuleiro fica sem eles. As secções 6 e 7 continuam a
aparecer com "0 diagrams below": os seus espécimes são texto corrido e filas de peças, não
tabuleiros, e o detector do crítico conta tabuleiros. Isso está afirmado no teste
(`test_no_section_heading_stands_on_a_page_without_its_specimens` isenta explicitamente as
secções 6 e 7 e falha se a isenção alargar).

**O preço, medido.** A folha passou de **12 para 13 páginas** e dois pés abriram:

```
.venv\Scripts\python.exe tools\measure_typography.py feet
  p3   folga ate a margem  79.9 mm
  p8   folga ate a margem 119.7 mm
```

O pé da p8 é a secção 8, cuja galeria é `keep_together` por exigência do Q4 nº 6 do próprio
crítico (os quatro tamanhos numa página) e precisa de uma página inteira; a cauda da secção
7 acaba a 40 % da p8 e nada mais lá cabe. Numa folha de espécimes, uma secção que começa em
página nova é convenção de casa; um título sem os seus espécimes é o defeito que o crítico
nomeou. Fico com o segundo fechado e o primeiro dito.

Os vãos **internos** não pioraram: o maior é 3,53 entrelinhas (p4, folha de espécimes, tecto
4) e as três páginas de livro ficam em 1,61 (`measure_typography.py holes`).

### 2.3 O rótulo `g` fora da fila — **FECHADO**

O rei Merida cobre o fundo da casa g1 em todos os recuos, e o ciclo 6 procurava um canto
livre **por rótulo**: sete letras assentavam em `y = 199,71 pt` e o `g` em `187,57` — 12,14
pt acima, dois terços de casa.

Uma fila de oito letras de coluna é uma **fila**, e uma fila assenta numa linha. `_shared_corner`
procura agora uma posição livre em **todas as oito casas** ao mesmo tempo — o canto mais
próximo da aresta do tabuleiro, a cada recuo, e só depois a aresta oposta — e as oito são
colocadas nessa posição. Quando o fundo está bloqueado nalgum sítio, as oito sobem para o
topo das **suas próprias** casas: cada letra continua dentro da casa que nomeia, nada é
desenhado por cima de peça nenhuma, e a fila mantém-se. `inside_coordinates_fit` usa a mesma
busca, de modo que uma posição sem canto comum devolve as coordenadas para fora em vez de
partir a fila.

```
.venv\Scripts\python.exe benchmarks\reports\critique\c5\inside_labels.py
  a b c d e f g h  todos em  y = 187.57
  baselines: min 187.57 max 187.57  spread 0.00 pt     (ciclo 6: 12.14 pt)
```

Olhei o espécime da p4 a 600 DPI: as oito letras numa linha, o `1` da fila de números na
mesma linha, o `g` livre acima da coroa do rei, nenhuma letra cortada.

---

## 3. O LaTeX, e uma correção a uma afirmação que este projeto tem repetido

`tools\build_latex.py` recompila e o log continua a dizer o que dizia:

```
compilado com pdflatex: benchmarks\reports\latex\livro.pdf
grep -c "Overfull|Underfull" livro.log  ->  0
```

**Esse zero não quer dizer o que temos andado a dizer que quer.** O documento usa
`multicol`, e `multicol` substitui `\tolerance` por `\multicoltolerance`, que vale **9999**
por omissão. Verifiquei em vez de o afirmar: recompilei o **mesmo** ficheiro com
`\multicoltolerance=200` (a tolerância normal do TeX) e o log passa a acusar
`Overfull \hbox (1.90569pt too wide)`. Com `\hbadness=99` e a tolerância por omissão, o log
não acusa nenhum *underfull*, o que quer dizer que nenhuma linha passa de badness 99 na
contabilidade do próprio TeX.

E aqui está o desacordo, que reporto em vez de esconder: o instrumento da §1.4, aplicado à
página LaTeX com caixas de coluna derivadas dela (a caixa da `amostra_F` não serve, a
geometria é outra), lê **banda 3,25× · desvio 0,475 · 38,9 % fora**, com a linha mais
frouxa em

> `Better was:   13…♘xc5   14.♘b3   ♘e6`

que na imagem da página se vê frouxa a olho. As duas medidas não podem estar as duas certas
sobre a mesma linha; a explicação mais provável é a do fim da §1.8 — os lances de `\mainline`
levam entre si uma cola própria, mais larga e mais elástica que o espaço de palavra, e o
instrumento, que só vê pixéis, conta-a como espaço de palavra. **Por isso não uso o número
do LaTeX como prova de nada.** Fica registado como o que é: um sítio onde o instrumento e o
compositor discordam, e uma razão para não estender esta medida a páginas de outra origem
sem a validar primeiro.

O que fica, dessa experiência, é útil na mesma: **"0 over/underfull boxes" é uma afirmação
sobre a tolerância configurada, não sobre a qualidade do espacejamento**, e este relatório
deixa de a citar como se fosse a segunda coisa.

---

## 4. Artefactos, e o que olhei

| artefacto | estado |
|---|---|
| `benchmarks/reports/proofsheet.pdf` | 13 páginas, regerado |
| `benchmarks/reports/proofsheet_rios.pdf` | 1 página, regerado |
| `benchmarks/reports/proofsheet_png/*.png` | 14 PNGs a 200 DPI, regerados |
| `benchmarks/reports/latex/livro.pdf` + `page_01.png` | recompilado |

**Olhei as 15 páginas, uma a uma, com o visualizador de imagem**, e não só as medi:

* p1–p2 — as 18 famílias. p2 acaba a 28,4 mm da margem (a secção 2 já não cabia).
* p3 — `2. Molduras` no topo com as seis molduras por baixo. Pé aberto, 79,9 mm.
* p4 — as quatro colocações de coordenada. **O espécime `inside` tem as oito letras de
  coluna numa linha**, com o `1` da fila de números alinhado com elas.
* p5 — os seis indicadores de lance.
* p6 — as quatro composições de marcas. As hastes passam por baixo das peças.
* p7 — secção 6 (figurino a 9/10/11/12 pt sobre a régua) e secção 7 a começar a meio.
* p8 — a cauda das 18 filas peça-a-peça. Pé aberto, 119,7 mm — o preço da §2.2.
* p9–p10 — 20/40/60/90 mm nos dois temas, os quatro na mesma página.
* p11 (hachurado), p12 (cinza), p13 (escuro) — a página de livro inglesa. As duas colunas
  fecham à mesma altura; cinco hífenes, nenhum a deixar duas letras a abrir linha; a linha
  de lances `6.♗g2 …` continua visivelmente frouxa e é a da §1.8.
* `rios_01.png` — a página portuguesa, a que o conjunto cego submete. É a página deste
  ciclo: os espaços lêem-se iguais de alto a baixo das duas colunas; hífenes em `de-cide`,
  `se-guinte`, `pá-gina`, `cus-tam`.
* `latex/page_01.png` — a exportação LaTeX, uma página, com a linha frouxa da §3.

---

## 5. A suite

```
.venv\Scripts\python.exe -m pytest -q
2987 passed, 1 skipped in 691.38s (0:11:31)

.venv\Scripts\python.exe -m pytest --collect-only -q                     2988 itens
.venv\Scripts\python.exe -m pytest tests\unit\typeset --collect-only -q   302 itens
```

Baseline do ciclo 6: **2965 passed, 1 skipped**. **Nenhum teste regrediu.** A contabilidade
da diferença, para não a deixar por explicar: `tests/unit/typeset` passou de 290 para 302
itens — são os 12 deste ciclo, listados abaixo — e os outros 10 apareceram em
`tests/unit/ui`, da frente que trabalha em paralelo nessa pasta. Não são meus e não lhes
toquei.

Os 12:

| teste | o que fixa |
|---|---|
| `test_the_badness_of_a_line_is_texs_badness` | badness cúbica, `inf_bad`, normalização pelos dois lados |
| `test_the_fitness_classes_are_texs_four` | as quatro classes, e que *decent/loose* = 0,901–1,498 cai **dentro** de 0,85–1,50 (a inclusão vale num sentido só, e é afirmada nesse) |
| `test_a_loose_line_under_a_tight_one_costs_adjdemerits` | `\adjdemerits` e `\doublehyphendemerits` |
| `test_a_word_carrying_punctuation_is_still_hyphenated` | o defeito (a) da §1.3, com as guardas ainda de pé |
| `test_the_hyphen_lands_inside_the_letters_and_not_in_the_punctuation` | `posi-tion;`, não `position-;` |
| `test_the_breaker_settles_the_page_without_the_desperate_pass` | o passe 4 nunca é usado |
| `test_total_fit_beats_first_fit_on_the_same_two_pages` | a afirmação do ciclo, contra um first fit no mesmo composer |
| `test_the_word_space_band_beats_every_reference_that_justifies` | a tabela da §1.4, e que a referência em bandeira continua a ser a E |
| `test_the_word_space_gate_fires_when_the_page_is_sabotaged` | a prova de vivacidade da §1.6 |
| `test_the_file_labels_of_an_inside_diagram_sit_on_one_line` | §2.3 |
| `test_no_section_heading_stands_on_a_page_without_its_specimens` | §2.2, com a isenção das secções 6 e 7 afirmada |
| `test_at_most_one_gap_class_comes_out_uneven` | §2.1, e o pé a 0,000 mm |

Os números do ciclo 6 que este ciclo tinha de não estragar, remedidos:

```
tools\measure_typography.py midshort   30 linhas de meio de paragrafo; 0 abaixo de 0.94; a mais curta a 1.00
tools\measure_typography.py wordspace  mais frouxa 2.14x  mais apertada 0.57x  2 acima de 2,0x  0 de 30 curtas
tools\measure_typography.py bottom     13 paginas, 0 com conteudo abaixo da margem. Pior transbordo 0.00 mm
tools\measure_typography.py feet       p11/p12/p13: diferenca 0.000 mm
tools\measure_typography.py holes      maior vao interno 3.53 entrelinhas (p4, folha de especimes; teto 4)
```

O `wordspace` mede a 200 DPI, onde o espaço nominal da página são **7,0 px**: os seus
valores estão quantizados em passos de ±7 % e o 0,57× dele é a mesma linha que o `wordband`,
a 300 DPI, lê em 0,80×. Mantive-o porque é o instrumento que o R1 nomeia; a §1.4 é a medida
com resolução para a pergunta deste ciclo.

---

## 6. Como re-executar tudo

```
.venv\Scripts\python.exe tools\typeset_proofsheet.py --png --dpi 200
.venv\Scripts\python.exe tools\build_latex.py
.venv\Scripts\python.exe tools\measure_typography.py wordband
.venv\Scripts\python.exe tools\measure_typography.py wordband --sabotage 4
.venv\Scripts\python.exe tools\measure_typography.py breaker
.venv\Scripts\python.exe tools\measure_typography.py wordspace
.venv\Scripts\python.exe tools\measure_typography.py midshort
.venv\Scripts\python.exe tools\measure_typography.py feet
.venv\Scripts\python.exe tools\measure_typography.py holes
.venv\Scripts\python.exe tools\measure_typography.py bottom
.venv\Scripts\python.exe benchmarks\reports\critique\c5\orphanheads.py
.venv\Scripts\python.exe benchmarks\reports\critique\c5\inside_labels.py
.venv\Scripts\python.exe benchmarks\reports\critique\c5\unjustified2.py
.venv\Scripts\python.exe -m pytest -q
```

`wordband` devolve 0 quando passa contra as cinco e 1 quando não passa — hoje devolve **1**,
e a saída diz porquê nas duas contas.

---

## 7. O que fica aberto, e a minha leitura honesta

0. **Contra a nossa própria página do ciclo 5 ganhamos duas das três, não as três**
   (§1.9). A que perdemos, a banda, é a que a recusa de justificar do ciclo 5 embelezava.
1. **A vantagem é real, e é menor do que a formulação do critério.** Em três estatísticas
   independentes, medidas por uma regra única sobre seis rasters, a nossa página é melhor
   do que **as quatro referências que justificam o texto**, e por margens que não são de
   ruído: banda 1,89 contra 2,55–3,57, desvio 0,160 contra 0,258–0,394, linhas fora da
   banda 9,1 % contra 31,4–51,1 %. Um leitor **vê** isto: as duas linhas extremas da A
   estão na mesma coluna a 165 px uma da outra e a diferença entre elas salta à vista; as
   nossas duas extremas lêem-se as duas como linhas de livro (§1.7). **Mas o critério diz
   "as cinco", e contra as cinco não passa**, porque a quinta compõe em bandeira e uma
   página em bandeira não pode perder esta estatística. Não vou pedir que se mude o
   critério a meio; digo o que medi e deixo a decisão onde ela pertence.
2. **A página inglesa não ganha a B** em duas das três estatísticas (§1.8), e a causa —
   parágrafos de duas linhas e um bloco de 15 fichas de notação numa medida de 63 mm — está
   medida e não tem remédio no compositor.
3. **`move → body` continua desigual na página inglesa** (§2.1), agora numa classe só, com
   o pé a 0,000 mm, e com os dois lados do compromisso medidos.
4. **A folha de espécimes ganhou uma página e dois pés abertos** (79,9 mm e 119,7 mm) para
   fechar o título órfão (§2.2).
5. **O instrumento não deve ser estendido a páginas de outra origem sem validação** (§1.8 e
   §3): na nossa exportação LaTeX ele discorda do próprio TeX, provavelmente porque conta a
   cola de `\mainline` como espaço de palavra.
6. **Continua aberto o nº 7 do ciclo 6** (conteúdo de xadrez errado em três pontos) e o
   nº 8 (fragmentação em parágrafos de ~2 linhas) — este último é, como a §1.8 mostra, a
   causa medida do pior número que a página inglesa tem.
