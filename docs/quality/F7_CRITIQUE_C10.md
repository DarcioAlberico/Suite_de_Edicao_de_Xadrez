# F7 — Crítica adversarial, ciclo 10

```
VEREDITO: APROVADO
CICLO: 10
FRENTE: F7 (Tipografia)
```

> **Nota de procedimento.** A Fase 1 inteira — ordenação, defeitos por amostra e o palpite
> real × gerado — foi medida, escrita e gravada em `benchmarks/reports/critique/c10/phase1.md`
> **antes** de abrir `GABARITO.json` e **antes** de abrir `F7_CRITIQUE_C8.md`,
> `F7_REPORT_C9.md` ou qualquer coisa em `benchmarks/reports/critique/`. O único documento
> lido antes da Fase 1 foi `docs/quality/CRITIC_CHARTER.md`. A tabela abaixo é cópia literal
> desse ficheiro. Não usei tamanho de ficheiro, data nem metadados PNG. Todos os números são
> meus, por scripts próprios; as saídas estão em `benchmarks/reports/critique/c10/`.
>
> **Escrevi só em** `docs/quality/F7_CRITIQUE_C10.md` e `benchmarks/reports/critique/c10/`.
> Verifiquei o caminho de escrita de cada instrumento antes de o correr: `measure_typography.py`
> só escreve em `tempfile.mkdtemp()`; **não corri `tools/typeset_proofsheet.py`** (o `main`
> reescreve os três PDF entregues) nem **`tools/build_blind.py`** (o `OUT` por omissão é
> `benchmarks/reports/blind/`, que apagaria o conjunto do ciclo 1) — recompus por chamada
> direta a `compose_book_page` / `compose_book_run` / `build_rios` gravando em
> `critique/c10/repro/`. Os md5 de `proofsheet.pdf`, `proofsheet_run.pdf` e
> `proofsheet_rios.pdf` estão inalterados depois de tudo o que corri.

---

## O teste às cegas deste ciclo veio vazado, e isso é um defeito do processo

Antes de eu abrir um único ficheiro, o enunciado da tarefa dizia-me: «Folio 45 moved
129.60 mm to the outer edge», «names only folios 45 and 47», e «their margin is 11.0 mm and
**ours is 14.0 mm**». A amostra E traz o fólio **45** e mede **13,97 / 14,10 mm** de margem;
a amostra A mede **10,92 / 11,05 mm**. Duas chaves independentes, ambas no enunciado.

Fiz a Fase 1 na mesma, e registei em `phase1.md` §5 a identificação por evidência **interna
à página** — tabuleiros de 405 × 405 px repetidos ao pixel, aresta direita com desvio-padrão
de 0,36 px, pés das colunas na mesma linha de base, e formato idêntico ao da amostra A, que é
o livro real que E imita. Chegaria a E de qualquer maneira. **Mas não foi um teste cego**, e
quem montar o conjunto do ciclo 11 tem de parar de citar o número que identifica a amostra.

O enunciado e o `GABARITO.json` também afirmam que as seis são páginas **recto**. Não são:
A = 204, B = 184, C = 188 são **versos** (fólio à esquerda), D = 147 é recto com fólio ao pé,
E = 45 é recto, e **F não tem fólio nenhum**. No ciclo cujo defeito reprovado era a paridade
do fólio, o conjunto de comparação não deixa comparar paridade de fólio. E os rótulos do
gabarito não batem com as páginas: `amostra_B` diz «p185» e a página imprime **184**;
`amostra_C` diz «p185» e a página imprime **188**; `amostra_F` diz «p109» e a página **não tem
fólio nenhum**. (À margem: o cabeçalho corrente da `amostra_C` é *Practical Chess Defence*,
que tanto quanto sei é título da **Quality Chess** e não da Everyman — vale conferir a
proveniência do corpus, porque o conjunto passa então a ter **duas** páginas Quality Chess e
nenhuma Everyman.)

---

## Comparação às cegas

*(preenchido ANTES de saber qual é a nossa — cópia literal de `critique/c10/phase1.md` §3)*

| Amostra | Posição | Justificativa |
|---|---|---|
| **A** | **1º** | A única página cuja hierarquia vertical está certa: o cabeçalho de lance em negrito fica a 1× entrelinha do parágrafo que ele introduz e a 2× do que o precede (33 px / 67 px medidos). Zero linhas-toco abaixo de 15 % da medida nas duas colunas. As duas colunas estão registadas na mesma grade de linha de base, valor a valor (1047, 1079, 1113 … idênticos nas duas). Cor de página densa e homogénea, olho antigo bem desenhado. |
| **D** | **2º** | A cor mais uniforme das seis sobre a maior amostra de linhas (43 linhas cheias numa coluna, dispersão 0,140 %), 46 linhas por coluna, fólio limpo ao pé. Perde para A por não ter diagrama nenhum na página — não dá para pontuar qualidade de diagrama — e por uma linha claramente frouxa. |
| **C** | **3º** | Composição densa e profissional, hierarquia correta, mas a página traz **duas corrupções visíveis de glifo**: «suff ocating» partido por um espaço espúrio e um filete horizontal atravessando «gxf6» em dois pontos distintos. Sete linhas-toco, duas delas a 7,3 % e 10,0 % da medida. |
| **E** | **4º** | O artefacto mais preciso do conjunto: três tabuleiros de 405 × 405 px idênticos ao pixel, margem direita com desvio 0,072 % / 0,087 % (metade da segunda melhor), pés das duas colunas exactamente na mesma linha de base (0,00 mm), legendas centradas a ±1 px, travessão e aspas corretos, peso do figurino casado com o do texto. Cai para o 4º por um defeito sistémico: não existe hierarquia vertical — todo bloco separado por exactamente 2× a entrelinha. Some-se duas hifenizações da última palavra do parágrafo e uma linha de dois caracteres («d5», 4,8 % da medida). |
| **B** | **5º** | Texto competente e bem justificado, pés nivelados, mas o conjunto de figurinos é muito mais pesado que a fonte de texto e produz manchas escuras em toda linha de análise; e **os diagramas não trazem coordenada nenhuma** num livro cujo texto nomeia casas a cada frase. |
| **F** | **6º** | Não é uma página de livro diagramada: sem fólio, sem cabeça corrente, formato US Letter, corpo enorme (altura-x 2,41 mm) rendendo 21 linhas por coluna, bandeira à direita muito desigual, e uma caixa de cantos arredondados com gradiente e sombra projectada — autoforma de processador de texto. |

**Identidade revelada: a nossa era a amostra E, classificada em 4º de 6.**

| Amostra | Origem (GABARITO) | Minha posição | Meu palpite real × gerado |
|---|---|---|---|
| A | referência — Quality Chess p204 (*Chess Structures*) | 1º | real, **digitalizada** ✔ |
| B | referência — Nunn p184 | 5º | real ✔ |
| C | referência — Aagaard p188 (*Practical Chess Defence*) | 3º | real, mas em derivação suja ✔ |
| D | referência — Gambit p147 | 2º | real ✔ |
| **E** | **nossa — `proofsheet_run` fólio 45 (recto), ciclo 9** | **4º de 6** | **gerada ✔** |
| F | referência — Dvoretsky 2025 | 6º | real, mal produzido ✔ |

> **Correcção a uma frase minha da Fase 1.** Escrevi ali «três tabuleiros de 405 × 405 px
> idênticos ao pixel». Re-medindo os quadros das seis amostras com o mesmo detector, os
> nossos dão **405 × 405, 405 × 406 e 405 × 405** px a 200 DPI, e **a amostra C é
> perfeitamente quadrada** (362 × 362). A frase sobrevalorizava-nos por um pixel e contra uma
> referência que empata; o que fica de pé é que os três tabuleiros da nossa página têm o mesmo
> tamanho entre si e a mesma coordenada x quando repetidos. Deixo a tabela como foi escrita e
> a correcção aqui, que é o que a §2.1 pede.

Acertei as seis origens. **A ordenação cumpre a §2.1**: 4º de 6, à frente de duas referências
publicadas, e — o que conta mais — **os sinais que a denunciaram são sinais de precisão**,
não de defeito: tabuleiro quadrado ao pixel, aresta direita de máquina, pés nivelados,
formato idêntico ao do livro que imita. Ver §2.1 abaixo para os três defeitos que apontei
nela e o que aconteceu a cada um.

### Vetor × digitalização, verificado por mim

O fundo das seis é exactamente 255 com desvio 0,000 e croma zero: ruído de papel não separa
nada. O teste que separa é a repetição de glifo — agrupo os componentes conexos por tamanho
de caixa e conto a fracção de bitmaps **byte-idênticos** a outro do mesmo grupo:

| | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| duplicatas exactas de glifo | **0,011** | 0,639 | 0,922 | 0,961 | 0,657 | 0,962 |

**Só a A é uma digitalização** — nenhum «e» dela é igual a outro «e». **O que isso moveu:**
retirei da conta contra A o tabuleiro fora de esquadro (413 × 407 px, 1,5 %) e o filete
direito rompido, que são artefactos de scanner e não de tipógrafo. Em troca, A é a única
amostra cuja micro-tipografia eu não posso auditar ao glifo, e disse-o na justificativa.

---

## §2.1 — os três defeitos que apontei na nossa, um a um

A carta é explícita: *«você não pode ter apontado nela nenhum defeito que não tenha apontado
também nas outras»*. Medi as cinco referências com o mesmo instrumento e **retiro dois dos
três**.

**«Hierarquia achatada» — RETIRO.** Escrevi que E é a única onde o cabeçalho de lance fica à
mesma distância do parágrafo que introduz e do que termina. Depois medi a cadência de linha
de base das outras cinco: **a Nunn corre a 31 px constantes** e **a Quality Chess
(*Practical Chess Defence*) a 33 px constantes**, 32 linhas seguidas, **sem um único vão
extra em lado nenhum** — os seus cabeçalhos de lance também estão equidistantes, com zero de
ar em vez de uma linha. Duas das cinco fazem exactamente o mesmo que nós. Só a *Chess
Structures* liga o cabeçalho para baixo (67 px acima, 33 abaixo). Gastar uma linha de branco
em vez de nenhuma é decisão de densidade, e a densidade não é defeito. **Acusação retirada.**

E corrijo também o «todo bloco» que escrevi: não é todo. Medido no raster da amostra cega,
quatro dos cinco vãos `move → body` estão a 1 slot (58 px) e **um está a 0** (coluna direita,
linha de base 1388 → 1417 = 29 px) — que é exactamente o `{'move->body': [0, 1, 1, 1, 1]}`
que o compositor reporta de si próprio. A minha frase da Fase 1 era mais absoluta do que a
página.

**«Hifeniza a última palavra do parágrafo» — não é exclusiva.** É real e é feia: E traz
`subsequently at-` / `tacked.` e, na última linha da página, `worth play-` / `ing for.`. Mas
a **Gambit** faz o mesmo na sua página — `losing the ini-` / `tiative.` — deixando um toco de
13,6 % da medida. Fica como não bloqueante nº 1.

**«Linha de dois caracteres» — não é exclusiva.** «d5» sozinho a 4,8 % da medida, segunda
linha de um bloco de lances em negrito. A **Dvoretsky** faz o mesmo com `13.♔g2`. Fica como
não bloqueante nº 2.

**Sobrou um sinal que é só nosso**, e não estava na minha lista da Fase 1 porque só o vi ao
medir os traços: **o roque `0–0` é composto com meia-risca**, o mesmo glifo do resultado
`1–0`. Ver não bloqueante nº 3. Não reprova, e digo porquê lá.

---

## O que re-verifiquei do ciclo 9, e o que encontrei

### R5 — o fólio alterna. CONFIRMADO, e o portão está vivo.

```
.venv\Scripts\python.exe tools\measure_typography.py folio        (3 execuções)
```

As três saem **byte a byte idênticas**, `7 fólios lidos, 0 defeito(s) -> PASSA`,
`exit 0`. Os sete estão onde a aritmética diz: 44/46 a `x = 14,00–17,30 mm` da esquerda,
45/47 a `x = 143,60–146,90 mm`, margem exterior **14,00 mm nos sete**.

```
.venv\Scripts\python.exe tools\measure_typography.py folio --sabotage 1
  7 fólios lidos, 2 defeito(s) -> NAO PASSA        exit 1
    p2: folio 45 (impar/recto) ... esta a 143.60 mm (x=14.00-17.30)
    p4: folio 47 (impar/recto) ... esta a 143.60 mm (x=14.00-17.30)
```

Dispara, e dispara **só nos dois rectos**; os três fólios da folha entregue não se mexem um
dígito; os sabotados caem exactamente em `x = 14,00–17,30 mm`, o número que o ciclo 8 mediu
na folha antiga. E os md5 dos três PDF entregues estão **inalterados** depois da sabotagem —
verifiquei, porque um instrumento que recompõe é um instrumento que pode escrever por cima.

**A guarda dos ≥ 7 fólios: provei-a eu, e não pela leitura do código.** Forcei
`mt.folio_spans` a devolver lista vazia e chamei `measure_folio`:

```
com folio_spans() forçado a vazio:  defects=0  passed=False
restaurado:                          defects=0  passed=True
```

Zero defeitos **e** reprovado. É o modo de falha certo, e é raro alguém o construir.

### O artefacto é o que o código produz — e em mais páginas do que foi alegado

Recompus por chamada directa e comparei o raster a 300 DPI. O relatório alega quatro páginas;
verifiquei **oito**:

```
proofsheet.pdf p11/p12/p13   raster diff mean = 0.0000, max = 0
proofsheet_rios.pdf p1       raster diff mean = 0.0000, max = 0
proofsheet_run.pdf p1..p4    raster diff mean = 0.0000, max = 0
```

**Proveniência da amostra cega, verificada:** `blind6/amostra_E.png` é `proofsheet_run.pdf`
p2 a 200 DPI — diferença máxima de **1 nível de cinza em 2 333 pixels**, todos dentro do
segundo diagrama. A amostra cega é o artefacto entregue, não um render de conveniência.

### `render_ours` — 0 de 4 colunas curtas

Não corri `build_blind.py` (escreveria em `benchmarks/reports/blind/`). Avaliei a condição do
portão directamente:

```
FULL_PAGE_SLACK = 1   FULL_PAGE_FOOT_MM = 0.01
mareco (en)  used/capacity=['52/53','52/53']  slack=[1,1]  short=0  spread=0.0000 mm -> PASSA
rios (pt)    used/capacity=['52/53','52/53']  slack=[1,1]  short=0  spread=0.0000 mm -> PASSA
```

**Sobre o «sétimo instrumento partido», adjudicado.** O ciclo 9 tem razão e o ciclo 8 não.
`compose(balance_last=True)` compõe o último espalhamento até `feather(tail, target=max(used))`,
e numa composição de uma página **todas** as páginas são o último espalhamento; o máximo
atingível é a altura da própria matéria, 52, e o portão exigia 53. Reproduzi: `capacity=53`,
`used=52`, nas duas fontes, nas duas colunas. Era **insatisfazível**, e disparava em ambas as
fontes por construção, não por medir alguma coisa. O ciclo 8 escreveu «o portão funcionou»;
funcionou como um `return False`. A leitura do ciclo 9 — *portão partido, a falhar do lado
seguro* — é a correcta, e a substituição (folga em slots + desnível dos pés) mede as duas
coisas que denunciaram mesmo a amostra do ciclo 1.

### `wordband` — reproduz ao dígito, e encontrei o que ele não diz

```
.venv\Scripts\python.exe tools\measure_typography.py wordband     (3 execuções)
-> as três byte a byte idênticas;  F nossa, pt  1.89x / 0.160 / 9.1 %;  exit code = 1
   contra as quatro que justificam: PASSA (3 de 3)
   contra as cinco:                 NAO PASSA (0 de 3)
```

Os três números do relatório são exactamente os meus, e o instrumento continua a **reportar
a sua própria falha**. Mas a mesma saída imprime uma linha que o §4 do relatório do ciclo 9
**não transcreve**, e é a linha que interessa a este ciclo:

```
F nossa, en (as 3 ultimas)   just 30/80  banda 0.80–1.84 = 2.30x  desvio 0.284  fora 10/30 (33.3 %)
```

Ver não bloqueante nº 4. É a correcção mais importante que trago, e não reprova — explico
porquê lá.

### `move → body` — o número está certo; o *trade-off* está contado por metade

Corri `unequal_gaps()` eu:

```
mareco (p11 / p12 / p13)  {'move->body': [0, 1, 1, 1, 1]}   pés [207.892, 207.892]  desnível 0.0000
rios (pt)                 {}                                 pés [207.892, 207.892]  desnível 0.0000
```

Idêntico ao reportado. **O número está certo.** O comentário do próprio `feather`
(`typeset_page.py` §~1765) documenta a medição nos dois sentidos — `equality kept, foot left
open pes [193.21, 207.89] desnivel 14.684 mm` contra `foot closed, one class uneven desnivel
0.000 mm` — e 207,89 − 193,21 = 14,68 confere com os 4 × 3,6713 = 14,685 do relatório. Não é
conta inventada.

**Mas o relatório conta só metade do *trade*.** Escreve *«mantê-los iguais significa pô-los
todos a 0»* — a direcção cara. Há a outra: pôr o único vão a 0 **a 1**. Medi a folga e ela
existe:

```
col0: used=52 capacity=53 folga=1        col1: used=52 capacity=53 folga=1
pés [207.892, 207.892]   pé desenhado 212.6 mm
pés que a corrida de facto atinge: [207.892, 211.563]
```

As duas colunas têm **um slot de folga**, e a corrida já compõe páginas com o pé a
**211,563 mm** = 207,892 + 3,671. Ou seja: subir aquele vão um slot igualava a classe ao custo
de **3,67 mm** de desnível, não de 14,685 — quatro vezes mais barato, e **menos** do que os
**4,19 mm** com que a própria *Chess Structures* fecha as suas colunas nesta amostra cega.
Continua a ser uma escolha legítima (a regra declarada do compositor é pé nivelado, e o ciclo
6 decidiu-a assim), e não é defeito na página. Mas a frase «a alternativa custa 14,685 mm» é a
metade cara de uma escolha de duas pontas, e quem lê o relatório não fica a saber que a outra
ponta custa 3,67.

### A margem de 14,0 mm contra os 11,0 mm da referência — não lê como defeito

Medi. Formato 160,9 mm: a nossa margem exterior é **8,7 %** da largura da página, a da Quality
Chess **6,8 %**. Para um livro de bolso deste formato, 14 mm está no meio da prática comercial
e 11 mm é o extremo apertado — **a referência é a excêntrica, não nós**. A consequência na
página é a medida da coluna: 63,4 mm contra 66,8 mm. Contei caracteres por linha à mão em
linhas cheias: **nós 47–49, a referência 41–50**. A nossa medida cai mais perto do meio da
faixa de conforto do que a dela. Olhei a página a 600 DPI à procura de uma coluna que
parecesse estreita ou de um pé que parecesse largo, e não é o caso.

**Não é defeito.** É uma decisão diferente e defensável, e o construtor nomeou-a contra si
sem lhe ser pedido, o que conta.

### Fase 3 — a folha a 400 e 600 DPI

Medi a caixa de tinta das 13 páginas de `proofsheet.pdf` e das 4 de `proofsheet_run.pdf`, e
renderizei a p3, a p8, a p13 e a corrida p2 a 400/600 DPI.

* As **quatro páginas de livro** fecham as duas colunas ao milésimo (`foot_spread`
  0,0000 mm nas três da folha, na `rios` e nas quatro da corrida) e a caixa de tinta dá
  **L 13,97 / R 14,10 / T 8,76 / B 20,07 mm** em todas — incluindo a página escura, que tive
  de medir com o limiar invertido (tinta clara sobre fundo 30) e que dá **os mesmos quatro
  números**.
* **p3 (96,5 mm de pé) e p8 (136,0 mm)** — as duas páginas de espécime que o ciclo 8 já
  adjudicou. Olhei a p8 a 400 DPI: são as dez últimas famílias de figurino, a secção está
  inteira, e o branco é o preço de não partir a grelha. Não é página de livro.
* **A página escura (fólio 46) não é a clara invertida.** Fundo #1B1F23, texto #E8E8E4,
  casas em dois cinzas médios em vez de hachura invertida, peças mantidas a preto-e-branco
  com contraste correcto, realce âmbar e seta vermelha. É desenho, não inversão. E o fólio
  46 está no canto **superior esquerdo**, que é o lado certo de um verso.
* A 600 DPI, o quadro do tabuleiro fecha limpo nos cantos, a hachura é recortada por baixo
  das peças (nenhuma peça deixa a trama passar), e os figurinos em linha assentam na linha
  de base do texto.
* **Uma coisa que o relatório do ciclo 9 afirma e não é verdade:** «nada fora da mancha». Na
  `proofsheet.pdf` **p4** o espécime `outside_right` põe tinta a **149,35–151,00 mm**, contra
  a aresta da mancha a 146,90 mm — **2,45 a 4,10 mm fora**, 715 pixels. É página de espécime
  e é o espécime que demonstra coordenadas do lado direito, portanto não bloqueia; mas a frase
  é falsa e foi escrita depois de «olhei as 18 páginas com os olhos».

---

## Defeitos bloqueantes

**Nenhum.**

Não escrevo isto de ânimo leve, e não é por cansaço de dez ciclos. Percorri a lista inteira
do §3.3 contra a página entregue e contra as cinco referências com o mesmo instrumento, e
todo o candidato a bloqueante ou (a) aparece também numa referência publicada, ou (b) não é
um defeito na página. A lista com o desfecho de cada um está no §2.1 acima e nos não
bloqueantes abaixo.

O único item que me fez hesitar de verdade está registado como não bloqueante nº 6 — a suíte
saiu vermelha numa das minhas três execuções, por não-determinismo real no subconjunto de
fontes. Pensei seriamente em reprovar por aí, invocando a §6 («métrica não reproduzível»), e
digo com precisão porque não o fiz:

* **A mediana das três execuções é `exit 0`**, e a §6 manda reportar a mediana. Duas de três
  passam; o teste isolado falha 1 vez em 12.
* **Não é um defeito na página.** A carta que me foi dada manda nomear **um** bloqueante e
  exige que ele seja *um defeito na página*. Este não toca no compositor, não toca no
  artefacto entregue (cujo raster verifiquei idêntico ao bit em oito páginas), e a sua causa
  está num ajudante de incorporação de fonte que o *pipeline* da página nem chama — confirmado
  por `grep`, não por suposição.
* **Os quatro portões que me pediram para re-verificar reproduziram ao dígito**, três
  execuções cada: `folio`, `folio --sabotage`, `wordband`, e a identidade ao raster.

Deixo-o nomeado, reproduzido fora do pytest, com a causa localizada em **duas** funções e com
a correcção escrita. E digo-o alto: **não ser bloqueante não é motivo para não o arrumarem** —
uma suíte que falha uma vez em doze é uma suíte em que ninguém acredita ao fim de um mês.

---

## Defeitos não bloqueantes

**1. Hifeniza a última palavra do parágrafo, duas vezes, e uma delas é a última linha da
página.** `subsequently at-` / `tacked.` (toco de 13,2 % da medida) e `worth play-` / `ing
for.` (13,6 %). Regra de manual: não se hifeniza a última palavra de um parágrafo. **A Gambit
faz o mesmo** (`losing the ini-` / `tiative.`), o que é a única razão de isto não bloquear.
Duas linhas no *breaker* fecham-no: proibir hífen na penúltima linha de um parágrafo e na
última linha de uma coluna.

**2. Uma linha de dois caracteres.** «d5» sozinha, 24 px = 4,8 % da medida, segunda linha do
bloco `1.d4 ♘f6 … 5.♘xd2 / d5`. A Dvoretsky faz o mesmo com `13.♔g2`.

**3. O roque `0–0` leva meia-risca, o mesmo glifo do resultado `1–0`.** Medido no raster a
200 DPI: o traço do roque tem **12 px de tinta por 1 px**, exactamente o do `1–0` da mesma
página, contra **6 px por 2 px** do hífen de `c5-d5` na mesma página. A **Gambit** — a única
referência do conjunto que compõe roque — usa `0-0` com o **hífen** (7 × 2 px). É o único
defeito de **detalhe tipográfico** que encontrei que é só nosso (o outro item só nosso é o
nº 7, e esse é um mecanismo que o ciclo 8 já adjudicou). Não bloqueia por duas razões que
digo por inteiro: uma
*figure dash* entre algarismos é defensável tipograficamente, e a 200 DPI, em tamanho de
leitura, lê-se como roque e não como resultado. Mas é 1,5 mm de tinta e a correcção é uma
entrada de tabela.

**4. A vantagem do espaço entre palavras está demonstrada na página portuguesa e NÃO na
inglesa — e a inglesa é a que foi submetida às cegas.** Este é o achado que quero que fique
no registo, porque o enunciado deste ciclo repete-o como facto verificado.

O mesmo `wordband`, a mesma regra, as mesmas caixas, medido por mim:

| página | n | banda | desvio | apertadas < 0,85 | frouxas > 1,50 | **fora** |
|---|---|---|---|---|---|---|
| A Quality Chess p149 | 38 | 3,57× | 0,327 | 39,5 % | 7,9 % | 47,4 % |
| B Nunn p50 | 35 | 2,55× | 0,258 | 25,7 % | 5,7 % | 31,4 % |
| C Gambit p116 | 81 | 3,00× | 0,263 | 29,6 % | 4,9 % | 34,6 % |
| D Everyman p215 | 47 | 3,50× | 0,394 | 31,9 % | 19,1 % | 51,1 % |
| **nossa, pt (`rios`)** | 22 | **1,89×** | **0,160** | 9,1 % | **0,0 %** | **9,1 %** |
| **nossa, en (fólio 45, a cega)** | 15 | 2,30× | 0,284 | 26,7 % | 6,7 % | **33,3 %** |

Passando o critério do próprio construtor à página inglesa: **1 de 3** contra as quatro que
justificam (ganha a banda a todas; perde o desvio à Nunn e à Gambit; perde o «fora» à Nunn),
e **0 de 3** contra as cinco. A alegação de «6,7 a 9,1 % contra 31,4 a 52,6 %» é verdadeira
da página portuguesa e **falsa da inglesa**, que empata com as duas melhores referências.

Duas coisas atenuam isto, e ambas são minhas:

* A **banda** — a estatística que mede a amplitude que a justificação introduz — continua a
  ser a **mais apertada das cinco páginas justificadas**, nas nossas **duas** páginas
  (1,89× e 2,30× contra 2,55×–3,57×). A vantagem existe; é menor do que foi vendida.
* A conta do «fora» junta duas coisas diferentes. Na página inglesa ela é dominada por
  **quatro linhas a 0,80×** — 20 % apertadas, que se lêem perfeitamente — e por **uma**
  frouxa a 1,84×. Nas referências a mesma conta inclui linhas a 0,54× e a 2,00×. Um leitor
  vê a linha frouxa; não vê a linha 20 % apertada. Pela metade que se vê, temos **1 linha
  frouxa em 15** contra 2 em 35, 4 em 81, 3 em 38 e 9 em 47 — e a página portuguesa tem
  **zero**.

Olhei a linha frouxa a 2,4×: é `6.♗g2 0–0 7.♘gf3 b6 8.0–0 ♗b7 9.♖c1 ♘bd7`, com espaços quase
o dobro dos da linha imediatamente abaixo. Está na página. A *Chess Structures* tem pior na
sua (`Better · was · 30.♘c3!? · and · a · possible`).

**O que peço:** que o §4 do relatório do ciclo 11 transcreva a linha `F nossa, en` e reformule
a alegação para *«a banda mais apertada de qualquer página justificada do conjunto, nas duas
páginas; e nenhuma linha frouxa na página portuguesa»*. É o que os números sustentam.

**5. O instrumento `wordband` tem duas fragilidades que ninguém tinha visto.**

* **`_our_pages()` lê as páginas erradas.** A linha é rotulada «as 3 ultimas» e o
  `_book_pages()` do mesmo ficheiro devolve `11,12,13`; mas `_our_pages` usa
  `pages=(10, 11, 12)` e depois `doc[number - 1]`, ou seja **1-based 10, 11, 12** — mede uma
  página de **espécime** (que sai `thin` e é descartada) e **nunca mede o fólio 46**. O
  agregado verdadeiro das três páginas de livro dá `2,56× / 0,303 / 33,3 %`.
* **`word_gap_cut` pode devolver a borda da própria janela.** O `leading` é estimado como a
  mediana dos passos entre **bandas de tinta**, que fundem linhas quando há blocos separados;
  uma variação de 10 % nessa estimativa move o limite inferior da janela de busca de 3 px para
  4 px, o que deixa de fora o pico dos vãos entre letras (contagem 193) e faz o `argmin` cair
  no **bin vazio do topo da janela**. Consequência medida: em `proofsheet_run.pdf` o `cut` sai
  **19 px** nas páginas 1–3 e **7 px** na página 4 — e **três das quatro páginas ficam
  `thin`, incluindo a p2, que é a amostra cega**. Com o `cut` forçado a 7, as quatro dão o
  mesmo número (2,30× / 0,284 / 33,3 %).
  O efeito na alegação: a **mesma** página nossa medida em três rasterizações dá
  **0,0 % (blind6, 200 DPI, 5 linhas medidas)**, **6,7 % (blind5, 200 DPI, 15 linhas)** e
  **33,3 % (PDF a 300 DPI, 15 linhas)**. O 6,7 % que o ciclo 8 usou para declarar a §5.1
  cumprida é uma dessas três. A docstring do próprio `word_gap_cut` critica o instrumento do
  crítico do ciclo 5 por «um limiar em que a resposta se senta»; faz o mesmo aqui.

**6. `subset_font` é genuinamente não-determinística, e a suíte fica vermelha cerca de uma vez
em doze.**

O relatório do ciclo 9 declara `2997 passed, 1 skipped, exit 0`. Corri a suíte completa **três
vezes** (§6 da carta), com `-p no:randomly` nas três:

```
run 1: 1 failed, 2996 passed, 1 skipped  em 640,21 s   exit 1   (2998 recolhidos)
run 2:           3000 passed, 1 skipped  em 628,61 s   exit 0   (3001 recolhidos)
run 3:           3009 passed, 1 skipped  em 657,26 s   exit 0   (3010 recolhidos)
FAILED (run 1) tests/unit/typeset/test_fonts.py::test_subset_is_deterministic
  At index 67 diff: b'\xef' != b'\xee'
```

**Mediana das três: `exit 0`.** Digo-o primeiro porque é o que a §6 manda reportar, e porque
seria fácil escrever só a run 1. Duas notas honestas sobre estes números:

* A **run 1 tem exactamente a colecção do ciclo 9** — 2998 recolhidos, 2997 executados. É a
  mesma suíte, os mesmos testes, na mesma ordem: ele verde, eu vermelho. Comparação directa.
* A colecção cresceu **2998 → 3001 → 3010** durante a minha sessão. Não são meus (não escrevi
  código); é **outra frente a mexer na árvore enquanto eu meço**, exactamente como o ciclo 9
  registou. O total da suíte não é uma medida estável desta entrega, e nem o número dele nem
  o meu deviam ser citados como se fosse.

Fui à causa e reproduzi-a **de propósito**, sem pytest, o que é uma prova mais forte do que
qualquer contagem de execuções: três chamadas a `subset_font(spec, wanted, flavor=None)`
separadas por 1,3 s devolvem **três SHA-256 diferentes**, com exactamente **três bytes** a
diferir (offsets 67, 183, 207), cada um por ±1 — a assinatura de um carimbo de tempo e do seu
*checksum*. `src/caissa/typeset/fonts.py::subset_font` constrói
`TTFont(str(font_path), fontNumber=0)` com o `recalcTimestamp=True` por omissão do fontTools,
e `source.save(buf)` grava `head.modified` com a hora corrente. O teste só passa quando as
duas chamadas caem no mesmo segundo.

Corri o teste **12 vezes isolado**: `FAIL PASS PASS PASS PASS PASS PASS PASS PASS PASS PASS
PASS` — **1 falha em 12**. Não é «às vezes»: é uma corrida entre duas chamadas e o relógio, e
o ciclo 9 correu uma vez e ganhou a moeda ao ar.

**Porque não bloqueia:** `subset_font` **não está no caminho da página**. Confirmei por
`grep`: só aparece em `caissa/export/epub.py`. O compositor emite por `tp.pages_to_pdf` →
`svgpdf.draw_svg(..., font_files=serif_files())` → `page.insert_text(fontfile=…)` do PyMuPDF,
e verifiquei que os rasters de oito páginas entregues são idênticos ao bit a uma recomposição
feita agora. **Porque tem de ser arrumado na mesma:** vive em `tests/unit/typeset`, que o
próprio relatório do ciclo 9 reivindica como o directório da F7, e a frase «0 falhas em toda
a suíte» é uma moeda ao ar. A correcção é um argumento:
`TTFont(str(font_path), fontNumber=0, recalcTimestamp=False)`.

**E há um segundo sítio, este pior, que entrego de graça à F8:**
`caissa/export/pdfwrite.py::_subset_font` tem exactamente a mesma falha — duas chamadas
separadas por 1,3 s dão `a686661f26db271f5cca` e `0008cdfb0b4ca5747912`. `grep -rn
recalcTimestamp src/` não devolve **nada**, ou seja nenhum dos dois subconjuntos o desliga.
Isso é o exportador PDF a carimbar a hora dentro de cada fonte que incorpora: nenhum PDF que
ele escreva é reprodutível ao byte.

*(Nota, para não inflar a acusação: os PDF do compositor também não são reprodutíveis ao
byte, mas isso **não** é da F7 nem do `subset_font` — a diferença são os nomes de recurso de
fonte que o PyMuPDF sorteia, `/cai79550` contra `/cai43661`. O raster é idêntico, e é o raster
que é a página.)*

**7. `diagram → move` sai a duas alturas na página da corrida — e a corrida é a amostra
cega.** A auditoria do próprio compositor di-lo, e o relatório do ciclo 9 não o transcreve:

```
mareco (p11/p12/p13)        {'move->body': [0, 1, 1, 1, 1]}
run 44-47 (a amostra cega)  {'diagram->move': [0, 1], 'move->body': [0, 1, 1, 1, 1]}
```

Medido no raster da amostra cega: da legenda `After 13.dxc5.` ao `13…bxc5?!` vão **62 px =
7,87 mm**; da legenda `After 21.♗xh7†.` ao `21…♘xh7 22.♗f6 ♕xc4` vão **31 px = 3,94 mm**.
O dobro, na mesma página, entre elementos equivalentes, e vê-se
(`critique/c10/views/E_diagram_to_move.png`). Não bloqueia porque é o mesmo mecanismo e o
mesmo *trade* que o ciclo 8 já adjudicou — o défice do `feather` gasto por classes inteiras
para fechar o pé — e porque a *Chess Structures*, na mesma amostra cega, escolhe o outro lado
e deixa as colunas a 4,19 mm. Mas a `proofsheet_run.pdf` é artefacto **novo** deste ciclo e é
a página que nos representa: a sua auditoria de vãos pertence ao relatório, e o custo da
alternativa tem de ser contado pelas duas pontas (ver o § «`move → body`»).

**8. Tinta fora da mancha na `proofsheet.pdf` p4**, 2,45 a 4,10 mm além da aresta direita,
contra a afirmação «nada fora da mancha». Página de espécime, e é o espécime de coordenadas à
direita. Ou o bloco passa a ser centrado pela caixa de tinta, ou a afirmação sai do relatório.

**9. Figurinos em linha os mais leves do conjunto** (número do ciclo 8, não re-medido por
mim). Fica no registo.

**10. `book_source_mareco` contradiz-se** (`Final remarks` culpa `17…♘d7`, lance que não
aparece na página). É autoria, categoria arrumada no ciclo 5, e continua a ser a página que
nos representa às cegas. O ciclo 9 declara que não lhe tocou e diz porquê.

---

## O que verifiquei e está sólido

Por dever da §5.5, e é a razão do veredito.

* **O bloqueante do ciclo 8 está fechado, e fechado no sítio certo.** Não foi o `decorate`
  que mudou: a `PageGeometry` passou a saber o que é um recto, e a **mancha inteira** espelha,
  não só o fólio. Medi os sete fólios das duas fontes, três vezes, saída idêntica.
* **O portão novo é vivo em três eixos e provei os três.** Dispara sob sabotagem e só nos dois
  rectos; reprova com zero defeitos quando não encontra fólios (forcei `folio_spans` a vazio);
  e não escreve por cima do artefacto entregue (md5 conferidos antes e depois).
* **Os testes importam o instrumento em vez de o reimplementar** — `_folios = mt.folio_spans`,
  `_folio_parity_defects = mt.folio_defects`. Oito testes novos, nomes verificados.
* **O artefacto é o que o código produz, ao raster, em oito páginas** — quatro mais do que o
  relatório alega. E a amostra cega **é** o artefacto entregue (diferença máxima de 1 nível de
  cinza em 2 333 pixels).
* **O construtor adjudicou correctamente contra o crítico anterior.** O portão de página cheia
  do ciclo 7/8 era `used == capacity` com `balance_last=True`, isto é, insatisfazível; o
  ciclo 8 concluiu «o portão funcionou» e enganou-se. Reproduzi `52/53` nas duas fontes e nas
  duas colunas. A leitura do ciclo 9 está certa e a substituição mede a coisa certa.
* **O *trade* que fica em aberto está declarado, com o número contra si, e o número confere**
  ao milésimo com o que o código já documentava (14,685 contra 14,684 mm). Encontrei a direcção
  mais barata que o relatório não conta — 3,67 mm em vez de 14,685 — e está no §
  «`move → body`» acima; é uma omissão de argumento, não um número errado.
* **A pergunta da margem foi respondida contra o próprio construtor.** Mediu 12 páginas
  seguidas da referência, concluiu que ela é simétrica — o que apoia a decisão dele — e a
  seguir reportou que a margem dela é 11,0 e a nossa 14,0. Verifiquei as duas: 10,92/11,05 e
  13,97/14,10. Está certo, e não lê como defeito na página.
* **A ordenação cega subiu de sentido, não só de posição.** 4º de 6 no ciclo 3, 3º no 5, 3º no
  8, **4º agora** — mas num conjunto onde as duas amostras atrás de nós são uma Nunn e uma
  Dvoretsky, e onde **os traços que denunciaram a nossa são traços de precisão**: três
  tabuleiros do mesmo tamanho na mesma coordenada, aresta direita com metade da dispersão da
  melhor referência, pés das colunas na mesma linha de base, formato idêntico ao do livro que
  imita. Nos ciclos 3, 5 e 8 a nossa foi identificada por um defeito. Neste, os três defeitos
  que lhe apontei ou aparecem numa referência publicada (dois) ou são 1,5 mm de tinta num
  traço (um).
* **A geometria de diagrama é boa, e corrijo aqui a minha própria Fase 1.** Escrevi lá «três
  tabuleiros de 405 × 405 px idênticos ao pixel»; medindo os quadros das seis com o mesmo
  detector, o quadro é **405 × 405, 405 × 406 e 405 × 405** px a 200 DPI — um pixel de
  arredondamento, 0,25 % num deles. E **a Aagaard também é perfeitamente quadrada** (362 × 362,
  0,00 %); a Dvoretsky sai a 0,18 %; só a Quality Chess está a 0,98 %, e essa é a
  digitalização. **Não somos os melhores em esquadro — empatamos.** O que continua a ser
  nosso e de mais ninguém no conjunto: os três tabuleiros da mesma página têm o mesmo tamanho
  ao pixel e caem na mesma coordenada x nas duas ocorrências da coluna direita; a hachura é
  recortada por baixo das peças; o quadro fecha limpo nos cantos a 600 DPI; há coordenadas
  (a Nunn não as põe); e há realce de casa e seta, que **nenhuma** das cinco referências
  mostra.
* **Os pés fecham a 0,000 mm nas quatro páginas de livro e nas quatro da corrida.** A
  *Chess Structures* fecha as suas a 4,19 mm.
* **O tema escuro é desenho e não inversão**, verificado a 400 DPI.
* **A galeria não se mexeu**, como o relatório diz: medi a caixa de tinta das dez páginas de
  espécime e todas começam a **13,97 ou 14,10 mm** — 14,0 mm mais ou menos um pixel a
  200 DPI. Com `inner == outer` o espelhamento é a identidade, e isso agora está medido e não
  assumido.
* **A dispersão da aresta direita é a mais apertada das seis** — 0,072 % / 0,087 % da medida
  (amplitude de **1 px** nas duas colunas) contra 0,126 %–0,221 % nas quatro referências
  justificadas — medida com o meu código, antes da revelação. Digo o *n*, porque é pequeno:
  13 e 4 linhas cheias nas nossas colunas, contra 8–43 nas delas. Numa página vectorial isto
  mede sobretudo a precisão do compositor, e é por isso que o pus como sinal de identificação
  e não como grande vantagem tipográfica.
* **`wordband` reproduz ao dígito, três vezes, e sai com exit 1.** O instrumento continua a
  não se auto-certificar.
* **O exportador LaTeX confere.** `livro.pdf` fólio 1 (ímpar/recto) tem o span `'1'` em
  `x = 145,16–146,91 mm` de 160,9 — acaba a **13,99 mm** da margem direita, o número que o
  relatório dá. E `livro.tex` é **byte a byte igual** ao `critique/c8/tex/base.tex`, `diff`
  vazio. Ressalva minha, pequena: o `livro.pdf` entregue tem **uma** página, portanto mostra
  um recto certo e **não** mostra alternância; se se quer os dois exportadores a concordar na
  mobília, o artefacto LaTeX precisa de pelo menos duas folhas.

---

## O que especificamente precisa mudar — para o ciclo 11, não como condição

Nada disto é condição de aprovação. É a lista, por ordem de custo/benefício, do que ainda
está errado na página ou no registo.

1. **`recalcTimestamp=False`** nos **dois** subconjuntos —
   `src/caissa/typeset/fonts.py::subset_font` e
   `src/caissa/export/pdfwrite.py::_subset_font`. Um argumento em cada. Depois disso
   `test_subset_is_deterministic` deixa de ser uma moeda ao ar, a frase «0 falhas em toda a
   suíte» passa a ser verdadeira, e os PDF do exportador passam a ser reprodutíveis ao byte.
   **Critério:** três execuções da suíte completa com `exit 0` nas três; e três chamadas a
   cada função, separadas por mais de um segundo, com o mesmo SHA-256.
2. **Guardas de hifenização no *breaker*:** nenhum hífen na penúltima linha de um parágrafo,
   nenhum hífen na última linha de uma coluna. **Critério:** zero ocorrências nas quatro
   páginas de livro e nas quatro da corrida, contadas dos spans do PDF.
3. **Roque com hífen, não com meia-risca.** **Critério:** a tinta do traço em `0-0` mede o
   mesmo que a de `c5-d5` na mesma página, e menos que a de `1–0`.
4. **`_our_pages()` tem de ler `_book_pages()`**, não `(10, 11, 12)`, e o rótulo tem de dizer
   quais páginas leu. **Critério:** a linha impressa nomeia os fólios 44/45/46.
5. **`word_gap_cut` não pode devolver a borda da janela.** Ou a janela começa abaixo do modo
   dos vãos entre letras, ou a função recusa e diz que não encontrou vale. **Critério:** as
   quatro páginas de `proofsheet_run.pdf` medem, e o `cut` da mesma página a 200 e a 300 DPI
   escala com o DPI.
6. **Transcrever a linha `F nossa, en`** no relatório e reformular a alegação da §5.1 para o
   que os números sustentam: *banda mais apertada de qualquer página justificada, nas duas
   páginas; zero linhas frouxas na portuguesa; empate com a Nunn e a Gambit na inglesa.*
   E trazer a página inglesa ao padrão da portuguesa é o trabalho tipográfico que resta.
7. **Auditar a `proofsheet_run.pdf` com `unequal_gaps()` no relatório** — ela tem uma classe
   desigual a mais (`diagram->move`) e é a página que vai às cegas.
8. **Contar o *trade* do `move → body` pelas duas pontas.** Com um slot de folga em cada
   coluna, igualar a classe **para cima** custa 3,67 mm de desnível, não 14,685 — e 3,67 mm é
   menos do que os 4,19 mm com que a Quality Chess fecha as suas colunas. Ou se mede e se
   escolhe com as duas contas à vista, ou a frase «a alternativa custa 14,685 mm» sai.
9. **Centrar o espécime de coordenadas pela caixa de tinta** na p4, ou retirar «nada fora da
   mancha» do relatório.
10. **Para quem montar o blind7:** não citar no enunciado o fólio nem a margem da nossa
    amostra; e se o conjunto disser «todas recto», que sejam todas recto. E conferir os
    rótulos do `GABARITO.json` contra o fólio impresso em cada página.

---

## Nota final, sobre rigor e obstrução

Dez ciclos, quatro reprovações. Vim procurar razão para reprovar e trouxe dez achados, seis
deles novos e três que nenhum crítico anterior tinha visto — um teste de determinismo que
falha uma vez em doze, um instrumento que lê as páginas erradas, e um limiar que se senta na
borda da própria janela. Retirei duas acusações minhas depois de medir as referências com o
mesmo instrumento, e corrigi duas frases minhas da Fase 1 que nos favoreciam. Nenhum dos que
sobram é um defeito **na página**, e os quatro portões que me mandaram re-verificar
reproduziram todos, três execuções cada, ao dígito.

O que está na página é isto: o fólio alterna e a mancha espelha com ele; as quatro páginas de
livro e as quatro da corrida fecham as duas colunas ao milésimo; três tabuleiros do mesmo
tamanho na mesma coordenada, com a hachura recortada por baixo das peças; a aresta direita
mais disciplinada do conjunto; um tema escuro desenhado e não invertido; realce e seta que
nenhuma referência mostra; e uma banda de espaço entre palavras mais apertada do que qualquer
das quatro páginas justificadas de editoras reais, nas nossas duas páginas. Os defeitos que
sobram — duas hifenizações finais de parágrafo, uma linha de dois caracteres, um traço de
roque com 1,5 mm de tinta a mais, um par de vãos a duas alturas — ou aparecem tal e qual numa
página publicada do mesmo conjunto, ou são menores do que os que apontei nas cinco
referências.

E o teste às cegas responde à pergunta da §1 melhor do que eu conseguiria argumentar: com o
conjunto à minha frente e sem saber qual era qual, pus a nossa **à frente da Nunn e da
Dvoretsky**, e identifiquei-a **pela precisão** — pelos três tabuleiros na mesma coordenada e
pela aresta direita de máquina — e não por ser pior. Nos ciclos 3, 5 e 8 foi ao contrário.

A §5.1 exige vantagem clara e não empate. Ela existe e medi-a eu: banda de espaço entre
palavras (a mais apertada das cinco justificadas, nas nossas duas páginas), dispersão da
aresta direita, e registo do pé de coluna a 0,00 mm contra 4,19 mm da referência que a página
imita. No esquadro dos tabuleiros **empatamos** e disse-o. A vantagem é menor do que foi
vendida — o §4 dos não bloqueantes diz exactamente quanto menor, com a página inglesa em
empate com as duas melhores referências. Mas «menor do que vendida» não é «não existe», e a
carta manda-me aprovar quando os bloqueantes acabaram.

Acabaram. **APROVADO.**

---

```
VEREDITO: APROVADO
CICLO: 10
FRENTE: F7 (Tipografia)
```

**A razão, numa linha:** o R5 está fechado na geometria e não no sintoma, com um portão que
provei vivo em três eixos e um artefacto idêntico ao bit em oito páginas; num teste às cegas
contra cinco editoras a nossa página ficou em 4º de 6 e foi identificada **pela precisão**,
não por um defeito; e nenhum dos dez achados que trago — nem o teste de determinismo
intermitente, nem a vantagem menor do que alegada na página inglesa — é um defeito na página
que uma das cinco referências publicadas não cometa também.
