# F7 — Tipografia · ciclo 6

> **Data:** 2026-09-07, com a passagem de verificação da §10 em 2026-09-08 ·
> **Máquina:** a de referência (Windows 11, `.venv` do projeto)
> **Entrada:** `docs/quality/F7_CRITIQUE_C5.md` — REPROVADO, quatro pedidos **R1–R4**.
> **Estado:** R1, R2, R3 e R4 fechados, cada um com a medida que a crítica nomeia.
> Dos oito não bloqueantes: **três fechados** (nº 4, 5 e 6), **um melhorado sem fechar**
> (nº 1) e **quatro declarados abertos** (nº 2, 3, 7 e 8), cada um com o número de hoje e
> a razão.
> **Verificação:** a **§10** foi escrita por um segundo agente, que não tocou no código e
> re-correu tudo. Todos os números das §§1–9 bateram; a suíte deu 2965/1/0 outra vez. As
> duas ressalvas que ele levanta, e a sabotagem do R1 que faltava, estão lá.

Todo número deste documento saiu de um comando que rodei nesta máquina **depois** da
reconstrução final dos artefactos, e o comando está ao lado do número. Onde a correção
custou outra coisa, o preço está escrito com o valor medido dos dois lados, não
arredondado nem omitido.

---

## 0. Como reproduzir

```
.venv\Scripts\python.exe tools\typeset_proofsheet.py --png   # a folha, os 12 PNG e a pagina rios
.venv\Scripts\python.exe tools\build_latex.py                # o PDF do LaTeX
.venv\Scripts\python.exe tools\compare_exporters.py          # R2, Q3 e Q5
.venv\Scripts\python.exe -m pytest tests -q                  # a suite inteira

.venv\Scripts\python.exe tools\measure_typography.py midshort   # R1
.venv\Scripts\python.exe tools\measure_typography.py wordspace  # R1 + Q4 nº 5
.venv\Scripts\python.exe tools\measure_typography.py figset     # R3
.venv\Scripts\python.exe tools\measure_typography.py counters   # R3, a causa
.venv\Scripts\python.exe tools\measure_typography.py figurine   # o preco do R3
```

Os scripts do crítico em `benchmarks\reports\critique\c5\` rodam contra os artefactos
novos sem alteração; uso `unjustified2.py`, `gapaudit.py`, `inside_labels.py`,
`orphanheads.py`, `register5.py` e `shortlines2.py` abaixo.

**Um deles deixou de medir o que mede, e não é defeito dele.** `figink2.py` recorta duas
bandas da p10 por ordenada fixa (`y = 511,5–520,5` e `521,5–531,0`), que eram as duas
linhas da corrida `13…♘xc5 14.♘b3 ♘e6 15.♕d2 ♕f6` na paginação do ciclo 5. A correção do
R1 re-quebrou esse parágrafo e as ordenadas caem hoje noutro sítio, de modo que o script
mede letras em vez de figurinos. A §3 mede a mesma grandeza — fração de tinta da caixa do
glifo, a 1200 DPI — a partir do **glifo** e não de um recorte, o que a torna independente
da paginação, e reproduz por esse caminho os 0,60 da dama e os 0,31–0,40 do cavalo que ele
mediu na página entregue.

**Artefacto novo:** `benchmarks\reports\proofsheet_rios.pdf`. O R1 pede a medida «nas três
páginas de livro **e** numa página composta a partir de `book_source_rios`» e o R4 pede
`Rfd1`, que é um lance que só essa fonte joga. Até agora a única renderização dela vivia
dentro do conjunto cego do crítico, onde a frente não a pode medir nem eu a posso olhar.
Agora é entregue.

---

## 1. R1 — uma linha de meio de parágrafo chega à medida · **FECHADO**

### 1.1 O que estava errado

`tools/typeset_page.py::break_paragraph` tinha um ramo que devolvia
`SetLine(..., justify=False)`: quando o otimizador não achava um arranjo dentro de
`MAX_SPACE_RATIO = 2.0`, a linha era composta rente à esquerda no espaço nominal. A causa
raiz é uma linha do custo, e é ela que explica o resto: uma linha **frouxa demais** e uma
linha **curta** custavam **o mesmo**, `_OVER_CAP_PENALTY = 1e6` para as duas. O otimizador
ficava livre de deixar 45 % da medida em branco no meio de um parágrafo para evitar uma
linha larga.

Reproduzi a medida do crítico antes de tocar em nada
(`critique\c5\unjustified2.py`):

```
mareco / proofsheet p10-12   37 linhas de corpo; 5 com a justificacao abandonada a meio
   fill 0,70 · 0,75 · 0,83 · 0,84 · 0,91
rios / blind3 amostra_F      42 linhas de corpo; 4 com a justificacao abandonada a meio
   fill 0,55 · 0,80 · 0,83 · 0,89
```

Dígito a dígito o que ele mediu.

### 1.2 O que fiz

O `break_paragraph` é agora Knuth–Plass sobre cola que **estica e encolhe**, com os pontos
de hifenização como quebras de primeira classe, e uma escada de penalidades cuja **ordem**
é o desenho inteiro:

```
badness  <<  _OUT_OF_BAND (1e6)  <<  _SHORT_PENALTY (1e9)
```

* uma linha dentro da banda preferida custa só a sua badness;
* uma linha **fora** da banda continua justificada e custa `_OUT_OF_BAND`;
* uma linha que **não chega à medida** custa mil vezes mais.

Uma linha frouxa ganha sempre de uma linha curta, que é a regra que faltava. O ramo
`justify=False` no meio de parágrafo deixou de existir: um `SetLine` não-final carrega
sempre `justify=True`.

Quatro peças a mais, todas com a sua razão medida:

1. **Encolhimento.** A cola tem agora `MIN_SPACE_RATIO = 2/3` — o encolhimento que o
   próprio TeX dá ao Times (`\fontdimen4` = 0,0833 em sobre um espaço de 0,25 em) — e um
   piso absoluto `ABS_MIN_SPACE_RATIO = 0,5`: meio espaço, que a 0,25 em é um oitavo de
   em, um espaço fino. O piso não é decorativo. Medi a folha inteira com ele em 0,5,
   0,6 e 0,667 (o encolhimento da própria fonte):

   ```
   piso 0,500   37 linhas justificadas   min 0,621   max 2,534
   piso 0,600   37 linhas justificadas   min 0,621   max 2,534
   piso 0,667   38 linhas justificadas   min 0,716   max 7,099
   ```

   No piso de 0,667 o parágrafo `Comparar as duas capturas é o exercício desta
   página…` — três fichas de notação protegidas numa medida de 63,45 mm — não tem
   arranjo nenhum e sai com uma linha a **7,10×** o espaço nominal. Com o piso a 0,5
   sai a **0,621×**, que é a linha mais apertada da folha e está declarada na §1.4.

2. **Hifenização dentro da otimização.** O ciclo 5 oferecia um hífen só à linha que o
   otimizador **já tinha escolhido** e depois re-quebrava a cauda gulosamente. Agora cada
   ponto de hifenização é uma quebra do problema, com a penalidade de Knuth (50), de modo
   que o custo de um hífen pode ser comparado com o custo de uma linha frouxa.
3. **Badness assimétrica.** `space_badness` normaliza cada lado pelo seu próprio limite,
   como em Knuth: um espaço tem mais folga para esticar do que para encolher, e a mesma
   *distância* ao nominal não é a mesma falta nos dois sentidos. **Nesta folha não muda
   nada**, e digo-o em vez de o deixar sugerido: medi as duas páginas com o custo
   simétrico `(r-1)²` e com o normalizado e as 37 linhas justificadas saem iguais, min
   0,621, max 2,534. Está aqui porque é o modelo certo e porque o custo simétrico
   escolheria um aperto duro sobre um esticão moderado assim que uma página lhe desse a
   escolha — não porque tenha corrigido um defeito medido.
4. **`Canvas.justified` deixou de testar o sinal da folga.** Era
   `stretchable = ... and slack > 0`; uma linha que o compositor tinha decidido apertar
   tem folga **negativa** e teria sido desenhada na largura natural, transbordando a
   coluna. Agora a decisão é do compositor (`line.justify`) e o desenho obedece.

### 1.3 A medida

`tools\measure_typography.py midshort` — o instrumento do crítico
(`critique\c5\midshort.py`) portado à geometria do PDF, com as suas quatro regras de
fim-de-parágrafo e uma quinta que ele próprio usou à mão na referência D (a linha seguinte
muda de peso), decidida aqui pelo nome da fonte do span e não a olho:

```
tres paginas de livro entregues (p10, p11, p12)
   30 linhas de meio de paragrafo; 0 abaixo de 0.94 da medida; a mais curta a 1.00
   nao contadas: opener 18, block end 15, weight 15, centred 9

benchmarks\reports\proofsheet_rios.pdf
   19 linhas de meio de paragrafo; 0 abaixo de 0.94 da medida; a mais curta a 1.00
   nao contadas: opener 4, block end 13, weight 0, centred 2
```

**Zero, e a mais curta chega exactamente à medida.** Critério do R1: zero abaixo de 0,94.
Referências A, B, C, D: zero em 204 linhas.

O script do crítico, sem alteração:

```
critique\c5\unjustified2.py
  mareco / proofsheet p10-12   36 linhas; 0 com a justificacao abandonada a meio
  rios   / blind3 amostra_F    39 linhas; 0 com a justificacao abandonada a meio
```

E na fonte, não só no artefacto:
`test_the_breaker_never_refuses_to_justify_a_mid_paragraph_line` espia
`break_paragraph` ao compor **as duas** páginas-fonte e exige `justify=True` em cada linha
que não seja a última do seu parágrafo: **36 linhas, 0 recusas.**

### 1.4 A conta que faltava, e o que ela custou

O R1 pede: *«Reportar, junto com o `wordspace`, quantas linhas o compositor recusou
justificar.»* `measure_wordspace` imprime-a agora, na mesma passagem e sobre as mesmas
páginas:

```
tools\measure_typography.py wordspace
  linha mais frouxa: 2.13x   mais apertada: 0.53x   linhas acima de 2,0x: 2
  linhas de meio de paragrafo que NAO chegam a medida: 0 de 30   (ciclo 5: 5 de 37, a pior a 0,55)
```

**O preço, dito inteiro.** O 1,73× do ciclo 4 era medido sobre as linhas que o compositor
justificou. Contando as que ele recusou, a página de ontem tinha uma linha em oito fora da
medida, a pior a 0,55 dela. A página de hoje não tem nenhuma, e paga por isso na faixa de
espaço entre palavras:

| | ciclo 5 | ciclo 6 | referências (fase 1 do crítico) |
|---|---|---|---|
| linha justificada mais frouxa | 1,73× | **2,13×** | B 2,33 · A 2,86 · C 3,00 · D 3,00 · E 4,00 |
| linha mais apertada | 1,00× | **0,53×** | — |
| linhas de meio de parágrafo abaixo de 0,94 | **9 de 79** | **0 de 49** | A 0 · B 0 · C 0 · D 0 |

O 2,13× fica abaixo do «2,2× numa linha» que o R1 autoriza (opção *b*) e dentro da banda
que as cinco referências ocupam; duas linhas em 30 passam de 2,0×. O 0,53× é o preço do
piso de encolhimento da §1.2 nº 1: é **uma** linha, `página: 13…♘xc5 deixa um isolado;
13…bxc5 deixa` na página portuguesa, e a alternativa medida é uma linha a **7,10×** no
mesmo parágrafo. Olhei-a a 200 DPI: lê-se como uma linha apertada, não como palavras
coladas. A dispersão que
daí resulta (2,13 ÷ 0,53 ≈ 4,0) é o pior número que a página tem contra o conjunto, e
digo-o aqui em vez de o deixar para a fase 1: **nesta métrica perdemos para quatro das cinco referências, e ganhámos a métrica que o R1 nomeia.**

O teste `test_no_justified_line_is_looser_than_twice_the_nominal_space` mudou de nome e de
teto — para `..._than_the_critics_ceiling`, `<= 2.3` — e **acrescenta** a asserção de que
nenhuma linha é recusada, porque um teto de espaço sem essa asserção é a métrica que o
ciclo 5 comprou.

### 1.5 O que a correção arrumou de graça

Com o encolhimento e a hifenização no otimizador — e com a largura da peça medida como é
desenhada, §3.2 — as duas páginas-fonte perdem **quatro linhas** de corpo: 37 + 42 = 79
passam a 36 + 39 = **75** (`critique\c5\unjustified2.py`, antes e depois). O pé não se
mexeu: **207,892 mm** nas três páginas de livro, o mesmo do ciclo 5, desnível **0,000 mm**
e resíduo `[0, 0]`. As colunas ficam a 52 das 53 casas da grade, iguais uma à outra e com
4,05 mm de folga até à margem inferior; é o que está declarado no teste da §7.

---

## 2. R2 — a paridade compara as peças · **FECHADO, e provado pela sabotagem do crítico**

### 2.1 Por que o portão era cego

`compare_exporters.py` normalizava os figurinos **para fora dos dois lados** porque não
havia o que comparar: o lado SVG desenha a peça como traçado vetorial e não deixava texto
nenhum, e o lado LaTeX deixava um glifo cujo `ToUnicode` dizia `†`. A normalização era o
sintoma; o R4 era a causa. Fechá-lo fecha este de graça, exactamente como a crítica diz.

### 2.2 O que fiz

Três comparações novas, e nenhuma delas exige que se acredite na outra:

1. **A página inteira, token a token, com as peças dentro.** Nada de figurino
   normalizado: os dois lados carregam a letra, e um cavalo trocado por uma dama é um
   token diferente. Uma linha cujos únicos tokens não-peça são dígitos de fileira e letras
   de coluna é uma fila de tabuleiro e continua a ser comparada como *diagrama*.
2. **`--- identidade das pecas`**: a lista ordenada dos glifos de peça das duas páginas,
   lida dos desenhos. Do lado LaTeX, os spans da família de xadrez; do lado SVG, as letras
   invisíveis — e a letra só conta como peça se estiver **sobre um traçado vetorial**, o
   que faz da comparação também uma verificação da camada de texto do R4. Um glifo por
   entrada, não um por span, porque o pdfTeX pode emitir dois figurinos vizinhos num span
   só e uma lista que os contasse como um deixaria uma troca esconder-se lá dentro.
3. **`--- identidade das pecas na fonte`**: o argumento de cada `\cfig{...}` do `.tex`
   gerado contra a lista `Run.kind == "piece"` do lado SVG — as duas fontes de verdade que
   a crítica nomeia, que saem da mesma passagem de marcação. Não precisa de fonte, de
   codificação nem de compilador para estar certa.

**Uma exclusão declarada.** As peças ficam **fora** da comparação de negrito/itálico e
são comparadas por `piece_runs`. A razão é de facto e não de conveniência: as famílias de
xadrez legadas são cortadas numa só série, `\cfig` força `\mdseries`, e um figurino LaTeX
dentro de um `\textbf` não é um span em negrito; o lado SVG engrossa o seu por dilatação
do desenho, que nome de fonte nenhum vê. O que se compara ali é **quais palavras** saem em
negrito; o que se compara em `piece_runs` é **qual peça** é cada figurino.

### 2.3 A medida

```
tools\compare_exporters.py
  pagina inteira, token a token ................. 198 tokens, identicos
  identidade das pecas, glifo a glifo ........... SVG 43, LaTeX 43, identicos
  identidade das pecas na fonte (\cfig) ......... 43, identicos
  legendas dos diagramas ........................ 3 legendas, identicas
  cabeca corrente ............................... iguais
  estrutura: corridas em negrito ................ 93 / 93, identicos
  estrutura: corridas em italico ................ 15 / 15, identicos
  TOTAL: 0 divergencia(s) nao declarada(s) + 1 declarada
```

São 198 tokens e não 222 porque o figurino deixou de ser um espaço e passou a ser a letra
do seu próprio lance: `Nf6` é um token onde antes eram dois.

### 2.4 A sabotagem, corrida e posta na suíte

A do crítico, à letra — copiei `livro.tex`, troquei **um** `\cfig{knight}` por
`\cfig{queen}`, compilei com duas passagens de `pdflatex` e apontei o script ao PDF:

```
--- pagina inteira, token a token
    divergencia tokens: 23  SVG 'Nf6'  vs  LaTeX 'Qf6'
--- identidade das pecas, glifo a glifo, nas duas paginas
    SVG 43 figurinos, LaTeX 43
    divergencia peca: 0  SVG 'N'  vs  LaTeX 'Q'
--- identidade das pecas na fonte: \cfig{...} contra a lista de corridas
    divergencia peca (fonte): 0  SVG 'N'  vs  LaTeX 'Q'
EXIT=3
```

**As três comparações apanham-na, cada uma por um caminho diferente, e o script sai com
3 nomeando o token.** Ontem imprimia «222 tokens, idênticos» e saía com 0.

Corri-a também **sem** o passo de `ToUnicode` — que é como um crítico que só compile o
`.tex` sabotado a vai encontrar — e o portão falha na mesma, com mais ruído: `EXIT=218`,
primeira divergência `SVG 'Nf6' vs LaTeX 'ƒf6'`. O portão não depende de um passo nosso
para ver a peça errada.

Na suíte, para as **seis** peças, com compilação real:

* `test_a_wrong_piece_in_the_tex_is_caught_by_the_gate[king|queen|rook|bishop|knight|pawn]`
  — troca o primeiro `\cfig` que ainda não é a peça errada, compila, e exige
  `compare(...) >= 1`;
* `test_a_wrong_piece_is_caught_in_the_source_without_compiling[...]` — a mesma troca
  contra a lista de corridas, sem compilador;
* `test_the_two_exporters_agree_on_the_whole_page` — e o par não sabotado tem de dar 0.

**15 passed** no subconjunto (`-k "wrong_piece or two_exporters_agree or latex_export"`),
em 164,5 s.

---

## 3. R3 — um só conjunto de figurinos · **FECHADO**

### 3.1 O diagnóstico, que não é o que parecia

A crítica descreve o defeito como *«dama e rei saem cheios, torre/bispo/cavalo/peão saem em
contorno»* e conclui que há dois conjuntos. O efeito é esse; o mecanismo é outro, e vale
dizê-lo porque é ele que se corrige. **Todos os seis vêm do mesmo conjunto branco**
(`fonts.artwork_char` → `_MARROQUIN_LIGHT`, o mesmo glifo que o diagrama usa para a peça
branca). O que os separava era o **negrito**.

Um traço aplicado a um contorno cresce para **dentro e para fora**: uma dilatação de `w`
engorda o anel de `w` e tira `w/2` de cada lado a **todas as contrapunções**. As
contrapunções da dama Merida são fios de cabelo entre as bolas da coroa; a 0,032 em, num
corpo de 8,6 pt, fecham. E como um traço de largura fixa acrescenta tinta em proporção ao
**perímetro** do desenho, e a dama Merida tem **16,9 mm** de perímetro externo contra
**8,9 mm** do rei numa caixa do mesmo tamanho (medido no contorno achatado, a 8,6 pt), o
mesmo traço acrescentava coisas muito diferentes a peças diferentes.

Medido a 1200 DPI, fração de tinta da caixa do glifo, mecanismo do ciclo 5:

| | K | Q | R | B | N | P |
|---|---|---|---|---|---|---|
| diagrama (sem traço) | 0,236 | 0,336 | 0,327 | 0,208 | 0,207 | 0,182 |
| em linha, negrito 0,032 | 0,423 | **0,584** | 0,599 | 0,378 | **0,380** | 0,339 |
| desvio | +0,187 | **+0,248** | +0,271 | +0,170 | +0,172 | +0,156 |

A dama a **0,584** e os cavalos a **0,380** — os 0,60 e 0,31–0,40 que o crítico mediu na
página entregue, reproduzidos aqui a partir do glifo. E a contrapunção da dama a **0,56**
da sua área em romano, que o ciclo 4 já tinha declarado sem ver que era o mesmo defeito.

### 3.2 O que fiz: a tabela de glifos

Duas mudanças, e a segunda é a tabela que a crítica pede.

1. **O negrito passou a crescer só para fora.** `figurine.figurine_svg` desenha agora três
   camadas: a silhueta (contornos externos) preenchida **e** dilatada; as contrapunções
   repostas ao **tamanho original** na cor do papel; e qualquer ilha dentro de uma
   contrapunção de volta em tinta. É o que um punção faz — engorda a silhueta e re-corta as
   contrapunções — e é expressável em SVG sem nenhum recurso exótico. A cor do papel entra
   por `Canvas.background`, portanto funciona igual no tema escuro.
2. **A tabela.** O corte deixou de ser especificado pela **largura do traço** e passou a
   ser especificado pela **tinta que acrescenta**: `FIGURINE_INK_GAIN_ROMAN = 0,030` e
   `FIGURINE_INK_GAIN_BOLD = 0,060`. `measure_family` resolve, **por peça**, a dilatação
   que produz esse ganho, a partir do perímetro, da área e da caixa do próprio contorno
   (soma de Minkowski, resolvida por bisseção uma vez por família, nunca no laço de
   desenho). Todas as seis peças ganham a mesma tinta, e nenhuma família precisa de números
   escritos à mão. `Contour.flatten/perimeter/area` são novos em `outlines.py`.

Um efeito colateral que era um defeito por si só: a dilatação entra agora na **largura
composta** (`measure_run` usa `metrics.advance_for` + `outset_for`, e `figurine_svg`
devolve a largura que desenha). O ciclo 5 media **todas** as peças pela largura da mais
larga e desenhava cada uma pela sua: uma linha de seis lances media até **3,1 mm** mais do
que desenhava, e a folga desaparecia invisível na margem direita.

### 3.3 A medida

`tools\measure_typography.py figset`, o critério da crítica à letra:

```
peca   diagrama   romano  negrito   d rom   d neg   (banda +-0.08)
K         0.235    0.264    0.293  +0.029  +0.058
Q         0.337    0.362    0.394  +0.026  +0.057
R         0.331    0.354    0.391  +0.023  +0.060
B         0.207    0.231    0.261  +0.024  +0.055
N         0.206    0.236    0.262  +0.030  +0.056
P         0.182    0.212    0.240  +0.030  +0.057

maior desvio contra o diagrama: 0.060  (criterio <= 0.080)
dispersao entre as seis pecas: negrito 0.154, diagrama 0.154
```

**0,060 contra um teto de 0,080**, e as seis peças ganham a mesma tinta (+0,055 a +0,060).
A dispersão do conjunto em linha é **exactamente** a do conjunto do diagrama: 0,154 nos
dois. É o mesmo conjunto, medido.

A causa, medida directamente (`... counters`, 1200 DPI):

```
peca     romano   negrito   razao   (criterio: >= 0.70)
K/Q/R/B/N/P                 1.00 · 1.01 · 1.00 · 1.00 · 1.00 · 1.00
```

Nenhuma contrapunção é tocada. Era 0,56 na dama e 0,73 no bispo.

**E olhei.** A p10 a 200 DPI: na corrida `Better was: 13…♘xc5 14.♘b3 ♘e6 15.♕d2 ♕f6`
as duas damas e os três cavalos são agora o mesmo desenho oco, e o mesmo na p6 nos quatro
corpos de 9, 10, 11 e 12 pt e na p12 (tema escuro), onde a contrapunção mostra o fundo
escuro através do glifo claro.

### 3.4 O preço, com o número dos dois lados

Um critério do **ciclo 1** cai, e digo-o sem rodeios porque é a segunda vez neste ciclo
que uma medida antiga se revela comprada.

O ciclo 1 pedia: densidade de tinta do figurino ÷ média dos dois vizinhos **≥ 0,85**, em
romano e em negrito. O ciclo 4 reportava 0,98 e 0,86.

```
tools\measure_typography.py figurine
  roman  figurino 23.1 %  vizinhos 'd' 34.2 % / 'x' 33.9 %  razao 0.68
  bold   figurino 26.3 %  vizinhos '.' 73.9 % / 'x' 43.6 %  razao 0.45
```

As duas exigências são **aritmeticamente incompatíveis** com este desenho, e a conta é
curta: a banda do R3 dá ao bispo 0,28 de tinta; os 0,85 dos vizinhos em negrito exigem
0,38, que é **0,17 acima do diagrama**, o dobro da banda. O 0,86 do ciclo 4 era alcançável
**preenchendo o desenho**: comprava-se a densidade fechando as contrapunções, que é
exactamente o padrão que a crítica nomeou três vezes nesta frente.

Escolhi o R3, que é o portão deste ciclo, e o piso do teste desceu para 0,60 romano /
0,40 negrito com toda esta explicação escrita ao lado dele
(`FIGURINE_INK_RATIO_FLOOR` em `test_proofsheet.py`). O que fica dito é o que é verdade:
**a peça branca de uma fonte de tabuleiro não fica tão densa como as letras em negrito ao
lado dela sem deixar de ser uma peça branca.** A saída de fundo seria uma fonte de xadrez
cortada para texto, e não é obra deste ciclo.

---

## 4. R4 — uma camada de texto que se pode pesquisar · **FECHADO**

### 4.1 Os dois lados, e por que falhavam por razões opostas

* **SVG:** o figurino é um traçado vetorial e não deixava texto nenhum. A linha extraída
  era `14…c4 runs into 15. d4, and 14… c8 15. c2`.
* **LaTeX:** o chessfss compõe o figurino a partir das casas que a codificação de texto
  chama `dagger`, `ellipsis` e `florin`, e o pdfTeX constrói o `ToUnicode` a partir desses
  **nomes de glifo**. A linha extraída era `1.d4 †f6 2.c4 e6 3.g3 …b4† 4.…d2 …xd2†` — e o
  `†` é o sinal de xeque **deste livro** e a `…` é a reticência de lance **deste livro**.
  Não é perda: é erro.

### 4.2 O que fiz

* **SVG.** `Canvas.hidden_text` põe a letra da peça por baixo do desenho em **modo de
  renderização 3** (invisível): entra na camada de texto e não pinta nada.
  `svgpdf._draw_text` honra `data-render-mode="invisible"`. O corpo da letra é resolvido
  para que a sua largura composta seja **exactamente** a do figurino — é isso que impede o
  extrator de ler um vão entre a peça e a casa e escrever `N f6`. A letra é a canónica
  inglesa (`figurine.SAN_LETTERS`), e um peão não leva nenhuma porque não leva nenhuma em
  notação algébrica.
* **LaTeX.** `latex.retag_figurine_text` reescreve o `ToUnicode` da fonte **de figurino**
  depois da compilação. Os códigos já estavam certos — o chessfss codifica a fonte de
  figurino de modo que `\symknight` é o carácter `N` — portanto o conserto é o CMap que os
  traduz mal, e não a fonte, a codificação ou o documento. A fonte **de tabuleiro** não é
  tocada e o relatório di-lo, por número de objecto, porque o documento carrega o mesmo
  `BaseFont` duas vezes. Se uma família futura codificar as peças noutro sítio, a função
  **levanta erro** em vez de escrever um CMap que diz outra coisa.

```
tools\build_latex.py
  camada de texto: 11 YGWHFT+Chess-Alpha: figurinos remapeados: 42->B 4B->K 4E->N 51->Q 52->R 70->P
  camada de texto: 14 YGWHFT+Chess-Alpha: fonte de tabuleiro: nao tocada
```

### 4.3 A medida

`page.get_text()` nos artefactos entregues:

| | linha de lances extraída | `Nf6` | `Nb3` | `Qxh7` | `Bxh7` | `Rc1` | `Rfd1` |
|---|---|---|---|---|---|---|---|
| SVG p10 | `1.d4 Nf6 2.c4 e6 3.g3 Bb4† 4.Bd2 Bxd2† 5.Nxd2` | 1 | 3 | 1 | 2 | 1 | — |
| LaTeX p1 | `1.d4 Nf6 2.c4 e6 3.g3 Bb4† 4.Bd2 Bxd2†` | 1 | 3 | 1 | 2 | 1 | — |
| SVG rios | `14.Nb3! Qc7 15.Qd2 Rfd8 16.Rfd1` | — | 3 | — | 1 | — | **2** |

Ontem: **zero** de tudo nos dois. `Rfd1` é um lance de `book_source_rios` e não da página
inglesa; uma busca não pode achar um lance que a página não imprime, e é por isso que
`benchmarks\reports\proofsheet_rios.pdf` passou a ser entregue em vez de existir só dentro
do conjunto cego. Os dois casos estão na suíte
(`test_the_svg_export_leaves_the_notation_searchable`,
`test_the_latex_export_leaves_the_notation_searchable`,
`test_the_portuguese_page_is_searchable_too`).

Mais uma asserção, porque uma camada de texto só vale se disser a verdade sobre o desenho
por baixo: `test_the_hidden_letter_sits_on_the_figurine_it_names` exige que cada letra de
peça caia **sobre um traçado vetorial** da mesma página.

**Nota para quem rodar `critique\c5\shortlines2.py`:** ele passa a imprimir, por baixo de
cada linha de lances, uma pseudo-linha como `| N BB BN|` a fill 0,92. É a camada
pesquisável — modo 3, tinta nenhuma. Não está na página; está na busca.

---

## 5. Os não bloqueantes

| nº | item | estado | número |
|---|---|---|---|
| 1 | `move → body` com espaços diferentes | **melhorado, não fechado** | §5.1 |
| 2 | título `2. Molduras` órfão dos seus espécimes | **aberto** | §5.2 |
| 3 | rótulo `g` fora da fila | **aberto, com a causa medida** | §5.3 |
| 4 | cabeça corrente sem acentos | **FECHADO** | §5.4 |
| 5 | traço diferente para a mesma construção | **FECHADO** | §5.4 |
| 6 | três estilos de separação de parágrafo | **FECHADO** | §5.5 |
| 7 | conteúdo de xadrez errado em três pontos | **aberto** | §5.6 |
| 8 | fragmentação (parágrafos de ~2 linhas) | **aberto** | §5.6 |

### 5.1 Vãos iguais para elementos equivalentes

`Atom.gap_class` regista o par de tipos de bloco que cada vão separa, e `feather` cresce
agora **classes inteiras** de vão sobre a página, numa ordem estável, em vez de correr em
roda dentro de uma coluna. Uma classe que não caiba em **todas** as colunas que a contêm
não cresce.

Isso não fecha o item, e a razão é geométrica, não de código. Na p10 a coluna esquerda
está **4 casas** curta e a direita está cheia; a esquerda tem quatro vãos `move → body` e a
direita tem um. Ou a classe não cresce e a coluna esquerda fica 4 casas curta, ou cresce só
onde há défice. Medi as duas:

```
classe cresce inteira ou nada:  pes [200.55, 207.89]  desnivel 7.342 mm  residuo [2, 0]
sobra distribuida em roda:      pes [207.89, 207.89]  desnivel 0.000 mm  residuo [0, 0]
```

Fiquei com o pé. O crítico verificou os **0,000 mm** e pô-los na lista do que está sólido;
não os troco por 7,34 mm para fechar um item que ele próprio classificou como não
bloqueante. `critique\c5\gapaudit.py` continua a marcar `move → body` a 2,0 casas quatro
vezes na coluna esquerda e 1,0 uma vez na direita, e o comentário em `feather` diz
exactamente isto.

### 5.2 O título órfão

`critique\c5\orphanheads.py`: `2. Molduras` continua a `y = 553,2` da p2 com **zero** dos
seus seis espécimes nessa página. Não mexi. É a mesma família de correção do Q4 nº 6
(amarrar a série ao título) mas sobre uma secção de seis tabuleiros de 52 mm, e mudá-la
re-pagina a folha inteira — quatro correções desta dimensão num ciclo em que R1 e R3 já
mudaram a quebra de linha e o desenho do glifo é mais risco do que o item vale. **Fica
aberto e nomeado.**

### 5.3 O rótulo `g`

`_free_corner` tenta agora **todos** os recuos da aresta preferida antes de qualquer canto
da aresta oposta — antes tentava os quatro cantos a cada recuo, e o primeiro recuo mandava
o rótulo para cima. Não mudou o número, e medi porquê: o rei Merida cobre o fundo da sua
casa em **todos** os recuos.

```
cobertura da silhueta do rei na caixa do rotulo (celulas de 96x96)
  recuo 0.020  br=171  bl=169  tr=0  tl=0
  recuo 0.095  br=424  bl=422  tr=70  tl=69
```

`critique\c5\inside_labels.py` continua a medir `a b c d e f h` em `y = 199,71` e o `g` em
`y = 187,57`, **12,14 pt acima**. A alternativa é `inside_coordinates_fit` recusar a
posição inteira — e o espécime da p4, que existe para mostrar o `inside` a funcionar,
passaria a mostrar coordenadas de fora. **Fica aberto**, com a causa medida.

### 5.4 A cabeça corrente

As duas cabeças correntes mudaram-se para junto das suas fontes
(`typeset_proofsheet.MARECO_RUNNING_HEAD` e `RIOS_RUNNING_HEAD`); `build_blind.py` e
`build_latex.py` importam-nas em vez de as reescreverem. A do português passou a
`Capítulo 4 — peões pendentes`: acentuada, e com **travessão**, que é o traço que o
subtítulo uma linha abaixo já usava (o item nº 5).

E a verificação que faltava, em `typography.missing_diacritics`, com duas regras
conservadoras — os ditongos nasais `-ão/-ões/-ães`, que em português são sempre acentuados,
e um vocabulário que se **colhe do próprio texto do documento** (`diacritic_vocabulary`),
de modo que o que o livro escreve com acento num sítio não pode aparecer sem ele noutro.
Nada com menos de 4 letras entra, porque `é` e `à` reduzem-se a `e` e `a`.

```
missing_diacritics('Capitulo 4 - peoes pendentes')  ->  ['Capitulo', 'peoes']
missing_diacritics(RIOS_RUNNING_HEAD)               ->  []
missing_diacritics('Family One - d4 and ...d5', 'en') -> []   (nao se adivinha outra lingua)
```

Três testes: a cadeia que embarcou falha, a nova passa, e **nenhuma** cadeia portuguesa que
a folha possa imprimir tem uma palavra a que falte um diacrítico.

### 5.5 Os três estilos de separação de parágrafo

Este saiu como consequência do R1 e de uma regra: `body0` significa **rente**, e rente só
está certo depois de algo **exibido** — um título, a linha do local, uma cabeça de secção,
um diagrama. Depois de outro parágrafo, um parágrafo abre **recuado**, como todos os outros
da página, porque o recuo é a única marca que diz que um novo começou. `book_blocks` aplica
a regra do lado SVG e `build_latex.latex_book` do lado LaTeX.

Três parágrafos mudaram (`Better was: 13…♘xc5…` na página inglesa, `Repare que a dama…` e
`O mesmo motivo aparece…` na portuguesa). O efeito na medida foi imediato: o
`measure_midshort` da página portuguesa passou de **1 linha assinalada** a 0. A linha era
`… em vez de completar o desenvolvimento.` e não era um falso positivo do detetor: o
parágrafo acabava ali e o parágrafo seguinte abria rente, uma casa abaixo, no mesmo peso,
de modo que **o leitor também não tinha por onde ver o fim**. Reverter a regra do recuo
reproduz o sinal.

**E encontrei uma divergência entre exportadores a olho, ao pôr as duas páginas lado a
lado:** o lado SVG recuava `Better was:` e o lado LaTeX abria-o rente, com o portão a
reportar 198 tokens, 43 peças e 93 corridas em negrito idênticos. Um recuo não é um token.
Está corrigido nos dois e o comentário no código diz de onde veio.

### 5.6 O que fica aberto sem desculpa

* **O conteúdo de xadrez de `book_source_rios`** continua errado nos três pontos que o
  crítico nomeou (o bispo em h7 do diagrama contra a linha impressa; `dxc3` com c3 vazia;
  `♗xc5` com o bispo preto em b7). É autoria, não composição, e não a toquei: os lances do
  lado LaTeX são validados por `python-chess` em `build_latex._play` e os da fonte
  portuguesa não passam por lá, porque essa página só sai pelo caminho SVG. **O caminho
  certo é validar os dois, e não é obra deste ciclo.**
* **A fragmentação** (56 %/60 % das linhas são finais de parágrafo) é escolha do texto
  fonte e não mexi nela.

---

## 6. Os cinco portões, re-medidos

| # | estado | número de hoje |
|---|---|---|
| Q1 | fechado | `marks`: 70 hastes, 0 contornos partidos; 93,5 % da tinta da peça de destino sobrevive; ponta 3,39:1, e ≥ 3,02:1 nos seis temas (menor: `warm`) |
| Q2 | fechado à letra | `inside`: 16 rótulos, 0 peças com entalhe; a falta nova do `g` continua aberta (§5.3) |
| Q3 | fechado, e agora com as peças dentro | 198 tokens, **43 peças**, 3 legendas, 93 negrito, 15 itálico, 0 divergências não declaradas |
| Q4 | 6 de 6, com o nº 5 no teto novo | `holes` 3,47 el (espécime) / 1,91 el (livro); `indent` 0 blocos; `wordspace` 2,13× **e 0 recusas**; `feet` 0,000 mm; `bottom` 12/12, transbordo 0,00 mm |
| Q5 | **assenta agora numa paridade que vê a peça** | §6.1 |

### 6.1 Q5 — a vantagem, e o que a sustenta agora

A candidata é a mesma do ciclo 4 — o mesmo livro pelos dois exportadores — e a diferença é
que o instrumento deixou de ser cego ao que interessa. O número não é «222 tokens
idênticos» com os figurinos normalizados para fora; é **198 tokens, 43 identidades de peça
glifo a glifo, 43 identidades de peça na fonte, 93 corridas em negrito e 15 em itálico,
0 divergências não declaradas — e a sabotagem que passava agora falha para as seis
peças, com compilação real, na suíte.**

Nenhuma das cinco referências tem dois caminhos de saída, portanto nenhuma pode apresentar
este número; e desta vez ele mede a coisa que um livro de xadrez é feito de.

As outras duas candidatas continuam declaradamente abertas, com os números de hoje:

* **Grade.** Registo transversal **100 %, fase máxima 0,0003 pt** (`critique\c5\register5.py`,
  o script do próprio crítico, nas três páginas). Ocupação 65 % / 78 % descontando as casas
  tomadas por diagrama. Empata com a amostra C em registo e perde-lhe em ocupação.
* **Símbolos de avaliação.** `∓`, `⩲` e `⩱` continuam sem sair como glifo único.

---

## 7. A suíte

```
.venv\Scripts\python.exe -m pytest tests -q
  2965 passed, 1 skipped in 784.20s (0:13:04)
```

**0 falhas.** O único `skipped` é o de sempre, o do compressor Brotli, e diz porquê.

Corrida **outra vez, do zero**, na passagem de verificação da §10:

```
.venv\Scripts\python.exe -m pytest tests -q
  ........................................................................s [ 89%]
  SKIPPED [1] tests\unit\typeset\test_fonts.py:253: WOFF2 precisa do compressor Brotli,
              que nao esta instalado neste ambiente. Instale com: pip install 'fonttools[woff]'
  2965 passed, 1 skipped in 725.62s (0:12:05)
  [exited with code 0]
```

Mesmas contagens, `exit 0`, e o mesmo único `skipped`. A diferença de tempo (784 s contra
726 s) é carga da máquina — outro agente compõe em `src\caissa\ui\` ao mesmo tempo.

Base do ciclo anterior: 2912 passed, 1 skipped, 0 failed. A frente F7 acrescenta **26
casos** (16 funções, duas delas parametrizadas pelas seis peças); o resto do crescimento
até 2965 não é meu — outro agente trabalha em `src\caissa\ui\` ao mesmo tempo e
`tests\unit\ui` recolhe hoje 110 casos. O subconjunto desta frente:

```
.venv\Scripts\python.exe -m pytest tests/unit/typeset -q -p no:randomly --collect-only
  290 tests collected     (91 deles em test_proofsheet.py)
```

Testes acrescentados neste ciclo (26 casos, 16 funções):

| teste | fecha |
|---|---|
| `test_no_mid_paragraph_line_stops_short_of_the_measure` | R1, no artefacto |
| `test_the_breaker_never_refuses_to_justify_a_mid_paragraph_line` | R1, na fonte, nas duas páginas |
| `test_a_line_the_breaker_justifies_is_drawn_to_the_measure` | R1, a identidade em que assenta |
| `test_the_inline_figurine_is_the_same_set_as_the_diagram` | R3, o critério do crítico |
| `test_the_bold_figurine_keeps_every_counter_open` | R3, a causa |
| `test_a_figurine_is_measured_at_the_width_it_is_drawn` | R3, o efeito colateral |
| `test_the_svg_export_leaves_the_notation_searchable` | R4, lado SVG |
| `test_the_latex_export_leaves_the_notation_searchable` | R4, lado LaTeX |
| `test_the_portuguese_page_is_searchable_too` | R4, `Rfd1` |
| `test_the_hidden_letter_sits_on_the_figurine_it_names` | R4, a camada diz a verdade |
| `test_the_two_exporters_agree_on_the_whole_page` | R2 / Q5 |
| `test_a_wrong_piece_in_the_tex_is_caught_by_the_gate` ×6 | **R2, a sabotagem do crítico** |
| `test_a_wrong_piece_is_caught_in_the_source_without_compiling` ×6 | R2, sem compilador |
| `test_no_portuguese_string_the_sheet_can_print_is_missing_a_diacritic` | não bloqueante 4 |
| `test_the_diacritics_check_catches_the_string_that_shipped` | não bloqueante 4 |
| `test_the_running_head_and_its_subtitle_use_the_same_dash` | não bloqueante 5 |

**Testes existentes que mudaram, todos com a razão escrita ao lado e o número dos dois
lados.** Digo-os um a um porque mudar um teste para ele passar é exactamente o que esta
frente já foi apanhada a fazer:

* `test_no_justified_line_is_looser_than_twice_the_nominal_space` →
  `..._than_the_critics_ceiling`, teto de 2,00× para 2,30× **e** uma asserção nova de que
  nenhuma linha é recusada. §1.4.
* `test_the_figurine_carries_the_colour_of_the_type_beside_it` — piso de 0,85 para 0,60
  romano / 0,40 negrito, com a conta que mostra que o 0,85 e a banda do R3 são
  incompatíveis. §3.4.
* `test_the_bold_figurine_keeps_its_counters` — ficou **mais** apertado: piso de 0,50
  para 0,98, porque nenhuma contrapunção é tocada.
* `test_the_two_exporters_set_the_same_page` — passou a chamar
  `latex.retag_figurine_text` no PDF que compila, que é o que `build_latex.py` faz ao
  artefacto. Falhou na primeira execução completa da suíte deste ciclo, com 217
  divergências e `SVG 'N' vs LaTeX '†'`: o portão novo **viu** que a
  camada de texto não tinha sido corrigida, que é exactamente o que ele existe para ver.
* `test_two_sources_give_two_genuinely_different_pages` — `used == capacity` passou a
  `capacity - used <= 1`, **mais** uma asserção nova de que as duas colunas acabam na
  mesma casa. A correção do R1 tira linhas compostas desta página e `balance_last`
  nivela as colunas pela mais alta: 52 de 53 casas nas duas colunas das duas fontes, pés
  a 207,892 mm — **o mesmo pé da página do ciclo 5** — e 4,05 mm de folga até à margem.
  Uma casa são 3,67 mm, e é a granularidade com que uma coluna pode acabar.

---

## 8. Olhei para todas as páginas

Depois da reconstrução final abri as **doze** páginas do PNG a 200 DPI, mais a página
`rios` e mais a página do LaTeX. O que a inspeção encontrou e nenhuma medida tinha
apanhado: o **recuo divergente entre exportadores** da §5.5. Está corrigido.

O que confirmei a olho: as damas e os cavalos da mesma corrida em negrito são o mesmo
desenho oco (p6 nos quatro corpos, p10 e p12); a linha mais apertada da folha, na página
portuguesa, lê-se apertada e não com as palavras coladas; a cabeça corrente portuguesa está
acentuada e usa o mesmo traço do subtítulo; nenhuma linha de meio de parágrafo pára antes
da margem direita em nenhuma das quatro páginas de livro.


### 8.1 A folha continua reproduzível ao span

O crítico regerou a folha do ciclo 5 três vezes e verificou que a camada de texto era
idêntica entre as três e idêntica à do artefacto entregue. Regerei-a três vezes, para
diretórios de rascunho, e comparei com o que está no disco:

```
regeracao 1: 1633 spans, sha256 8aedc446a25f2852, 9139 chars
regeracao 2: 1633 spans, sha256 8aedc446a25f2852, 9139 chars
regeracao 3: 1633 spans, sha256 8aedc446a25f2852, 9139 chars
artefacto  : 1633 spans, sha256 8aedc446a25f2852, 9139 chars
```

São 1633 spans e não 1507 porque a camada pesquisável do R4 acrescenta um span invisível
por figurino. O que está no disco continua a ser o que o código produz.

> **Ressalva da verificação (§10.1).** A invariante — quatro regerações e o artefacto todos
> com **1633 spans** e todos com o mesmo hash — foi reproduzida. A *cadeia* `8aedc446a25f2852`
> não, porque depende do serializador de span de quem a imprimiu: com outro serializador dá
> `ff3b32ecc2338112`, também igual nos quatro. **O hash só compara consigo mesmo**; quem o
> reproduzir noutro script deve esperar outra cadeia e exigir apenas que as quatro coincidam.

---

## 9. O que continua em aberto, sem rodeios

1. **A faixa de espaço entre palavras piorou** de 1,73× para 2,13× / 0,53×, que é o preço
   declarado do R1 e a métrica em que passamos a perder para quatro das cinco referências.
   §1.4.
2. **A razão de tinta do figurino** caiu de 0,86 para 0,45 em contexto negrito. É o preço
   declarado do R3, e o número antigo era comprado fechando as contrapunções. §3.4.
3. **`move → body` continua com dois espaços na mesma página** (2,0 e 1,0 casas), porque a
   alternativa medida é 7,34 mm de desnível no pé. §5.1.
4. **`2. Molduras` continua órfã dos seus seis espécimes.** §5.2.
5. **O `g` continua 12,14 pt fora da fila**, e a causa está medida. §5.3.
6. **O conteúdo de xadrez de `book_source_rios` continua errado em três pontos**, e a
   página portuguesa continua sem validação de lances. §5.6.
7. **`∓`, `⩲` e `⩱`** continuam sem glifo próprio. §6.1.
8. **O «livro» dos dois exportadores continua a ser uma página.**

---

## 10. Verificação independente

As §§1–9 foram escritas por quem fez as correções. Esta secção foi escrita depois, por
outro agente, que **não** mexeu no código e cuja única tarefa foi re-correr tudo e
confrontar cada número com o que a máquina devolve. Está aqui porque esta frente já
embarcou três alegações falsas e um portão cego, e um relatório em que o autor é a única
testemunha não vale o papel.

### 10.1 O que foi re-corrido, número a número

Todos os comandos abaixo correram **depois** da suíte, contra os artefactos no disco.

| medida | comando | relatado nas §§1–9 | medido agora | bate |
|---|---|---|---|---|
| R1, artefacto, 3 páginas de livro | `measure_typography.py midshort` | 30 linhas, 0 abaixo de 0,94, mais curta 1,00; não contadas opener 18 / block end 15 / weight 15 / centred 9 | idem, campo a campo | ✔ |
| R1, artefacto, página `rios` | `... midshort --pdf ...proofsheet_rios.pdf --pages 1` | 19 linhas, 0 abaixo de 0,94, mais curta 1,00; opener 4 / block end 13 / weight 0 / centred 2 | idem | ✔ |
| R1, na fonte | `critique\c5\unjustified2.py` (do crítico, sem alteração) | mareco 36 linhas / 0 abandonadas; rios 39 / 0 | idem | ✔ |
| R1, a conta que faltava | `... wordspace` | mais frouxa 2,13× · mais apertada 0,53× · 2 acima de 2,0× · **0 de 30** recusadas | idem | ✔ |
| R2, paridade | `compare_exporters.py` | 198 tokens · 43 peças · 43 na fonte · 3 legendas · 93 negrito · 15 itálico · 0 não declaradas | idem, `EXIT=0` | ✔ |
| R2, sabotagem | copiar `.tex`, um `\cfig{knight}`→`\cfig{queen}`, 2× `pdflatex` | `EXIT=3`, as três comparações apanham | idem (transcrito na §10.2) | ✔ |
| R2, sabotagem sem `ToUnicode` | idem, sem `retag_figurine_text` | `EXIT=218`, `SVG 'Nf6' vs LaTeX 'ƒf6'` | idem | ✔ |
| R3 | `... figset` | desvio máximo **0,060** contra teto 0,080; dispersão 0,154 nos dois conjuntos | idem, linha a linha | ✔ |
| R3, o script do crítico | `critique\c5\setaudit.py` | — | K/Q/R/B **todas** `outline (white-piece glyph)` nas três famílias: unicode 0,250/0,305/0,334/0,272 · merida 0,278/0,410/0,379/0,305 · alpha 0,277/0,305/0,346/0,342 | ✔ |
| R4 | `page.get_text()` nos dois PDF | tabela da §4.3 | idem, contagem a contagem | ✔ |
| não bloq. 2 | `critique\c5\orphanheads.py` | `2. Molduras` a `y=553,2` da p2 com 0 espécimes | idem | ✔ |
| não bloq. 3 | `critique\c5\inside_labels.py` | `g` a 187,57 contra 199,71, **12,14 pt** | idem | ✔ |
| não bloq. 1 | `critique\c5\gapaudit.py` | `move → body` a 2,0 quatro vezes na esquerda e 1,0 uma na direita | idem | ✔ |
| não bloq. 4 e 5 | `typography.missing_diacritics` | `['Capitulo', 'peoes']` na cadeia que embarcou, `[]` na nova | idem; `RIOS_RUNNING_HEAD == 'Capítulo 4 — peões pendentes'` | ✔ |
| suíte | `pytest tests -q` | 2965 passed, 1 skipped, 0 failed | idem, `exit 0`, 725,62 s | ✔ |

**Nenhuma discrepância.** Duas notas de honestidade sobre a própria tabela:

* **O `sha256` da §8.1 não é reproduzível a partir deste documento**, e não é defeito da
  folha. Reger a folha três vezes e comparar com o disco dá **1633 spans nos quatro** e um
  hash igual nos quatro — mas o meu serializador de span não é o da §8.1, por isso a minha
  cadeia é `ff3b32ecc2338112` e não `8aedc446a25f2852`. **A invariante é que os quatro são
  iguais, e essa verifica-se;** a cadeia em si só compara consigo mesma.
* **O artefacto do LaTeX era mais velho que `figurine.py`** (23:10 contra 23:22), o que é
  motivo suficiente para não acreditar nele. Reconstruí-o. O `.tex` sai **byte a byte
  idêntico** (8154 bytes, `cmp` limpo) e o PDF sai com a **mesma camada de texto** (544
  spans, mesmo hash); só diferem `/ID` e `/CreationDate`. A paridade continua a dar 0. O
  artefacto estava certo; agora está também datado depois da fonte.

### 10.2 A sabotagem do crítico, transcrita da corrida de verificação

Copiada do `.tex` entregue, **um** `\cfig{knight}` de dezasseis trocado por `\cfig{queen}`,
duas passagens de `pdflatex`, `retag_figurine_text` como `build_latex.py` faz, e o portão
apontado ao PDF sabotado:

```
livro.tex: 16 \cfig{knight} before, 15 after; one swapped to \cfig{queen}
pdflatex pass 1: returncode 0
pdflatex pass 2: returncode 0
retag_figurine_text: {'11 YGWHFT+Chess-Alpha': 'figurinos remapeados: 42->B 4B->K 4E->N 51->Q 52->R 70->P',
                      '14 YGWHFT+Chess-Alpha': 'fonte de tabuleiro: nao tocada'}

--- pagina inteira, token a token (reticencia normalizada nos dois lados)
    divergencia tokens: 23  SVG 'Nf6'  vs  LaTeX 'Qf6'
--- identidade das pecas, glifo a glifo, nas duas paginas
    SVG 43 figurinos, LaTeX 43
    divergencia peca: 0  SVG 'N'  vs  LaTeX 'Q'
--- identidade das pecas na fonte: \cfig{...} contra a lista de corridas
    divergencia peca (fonte): 0  SVG 'N'  vs  LaTeX 'Q'
--- legendas dos diagramas
    3 legendas, identicos.
--- cabeca corrente
    SVG   'Family One – d4 and...d5'
    LaTeX 'Family One – d4 and...d5'   iguais
--- estrutura: quais corridas saem em negrito
    SVG 93 tokens em negrito, LaTeX 93
    93 negrito, identicos.
--- estrutura: quais corridas saem em italico
    SVG 15 tokens em italico, LaTeX 15
    15 italico, identicos.
--- a divergencia declarada: a reticencia
    glifo   SVG '…'   LaTeX '...'   DIVERGENCIA DECLARADA
    espaco depois dela   SVG 0.00 pt   LaTeX 0.00 pt   ok

TOTAL: 3 divergencia(s) nao declarada(s) + 1 declarada (a reticencia).
EXIT=3
```

E a mesma sabotagem **sem** o passo de `ToUnicode`, que é o caminho de quem só compile o
`.tex`. O portão falha na mesma, e a saída mostra de passagem o mapeamento que o R4 veio
corrigir — o cavalo a sair `†` e o bispo a sair `...`:

```
    divergencia tokens: 23  SVG 'Nf6'      vs  LaTeX 'ƒf6'
    divergencia tokens: 26  SVG '3.g3'     vs  LaTeX '3.g3...b4†'
    divergencia tokens: 28  SVG '4.Bd2'    vs  LaTeX '5.†xd2'
EXIT=218
```

### 10.3 Uma sabotagem que faltava: a do R1

O R2 tinha a sabotagem do crítico. O R1 não tinha nenhuma — tinha só a afirmação de que o
portão dá zero, que é o que um portão cego também dá. Fi-la, porque «zero» sem prova de que
o instrumento **sabe** dar outra coisa é exactamente a falha que esta frente já cometeu.

A correção do R1 é um número: `_SHORT_PENALTY = 1e9` contra `_OUT_OF_BAND = 1e6`, de modo
que **uma linha frouxa ganha sempre a uma linha curta**; o ciclo 5 cobrava 1e6 aos dois.
Repus o custo do ciclo 5 e voltei a compor as duas páginas-fonte:

```
as shipped:  _SHORT_PENALTY=1e+09  _OUT_OF_BAND=1e+06
  mid-paragraph lines composed .......... 36
  refused justification (justify=False) . 0
  unstretchable short lines ............. 0

sabotaged:   _SHORT_PENALTY=1e+06  _OUT_OF_BAND=1e+06   (o custo do ciclo 5, à letra)
  mid-paragraph lines composed .......... 38
  refused justification (justify=False) . 0
  unstretchable short lines ............. 4
      fill 0.03 |E|
      fill 0.12 |6.[B]g2|
      fill 0.14 |página:|
      fill 0.16 |compare|

GATE IS LIVE: short lines 0 -> 4
```

**Quatro linhas de meio de parágrafo a 3 %, 12 %, 14 % e 16 % da medida voltam no instante
em que o custo volta** — a mesma família de defeito que o crítico mediu a 0,55. O zero da
§1.3 é um zero medido, não um zero por omissão.

### 10.4 Onde o instrumento do crítico dá falso positivo, e como sei que é falso

`critique\c5\midshort.py` lê píxeis e não sabe o que é uma legenda. Corri-o com as suas
**próprias** caixas de coluna sobre a página `rios` re-rasterizada a 300 DPI — a mesma
geometria do `blind3\amostra_F`, `(1901, 2700)` nos dois — e ele acusa três linhas na
coluna direita:

```
  col L: measure 746px, 14 mid-paragraph lines; 0 below 0.94 fill (0 %)
  col R: measure 747px, 11 mid-paragraph lines; 3 below 0.94 fill (27 %); deepest 0.581
        fill 0.581  y=2345
        fill 0.766  y=2054
        fill 0.771  y=927
```

Fui ver o que está nessas três ordenadas, pelo texto do PDF, e **nenhuma é uma linha de
corpo**:

| y (px) | o que lá está | o que é |
|---|---|---|
| 2345 | `Resumo` | **título** |
| 2054 | `A posição de partida da estrutura.` | **legenda de diagrama** |
| 927 | `A mesma ideia, um ataque adiante.` | **legenda de diagrama** |

A coluna direita da página portuguesa é a coluna dos diagramas; um detector de píxeis conta
lá legendas e títulos como se fossem corpo. É por isto que a §1.3 usa `measure_midshort`,
que decide o fim de parágrafo por peso de span e por centragem e não por altura de banda —
e é por isto que o número que **fecha** o R1 é o da instrumentação do compositor
(`unjustified2.py`, do próprio crítico: **0 recusas em 36 e em 39**), que não tem de
adivinhar o que é uma legenda porque o compositor sabe.

Faço a mesma ressalva ao contrário: o `figink2.py` do crítico, que a §0 já diz ter deixado
de apontar para a linha certa, dá hoje dois «PIECE GLYPH: SOLID». Fui ver as caixas: têm
**71×97 px** contra os **109–118×109 px** dos figurinos verdadeiros — são letras em negrito
que a heurística `w > 0.7*h` do script deixa passar. Na mesma corrida os três cavalos dão
0,269 / 0,271 / 0,270 e as duas damas 0,390 / 0,394. O ciclo 5 media cavalo 0,31–0,40 e
dama 0,60, com a dama **cheia**.

### 10.5 Olhei outra vez, e a todas

Re-rasterizei as **catorze** páginas dos três PDF entregues a partir do PDF (não dos PNG
do disco) e abri-as uma a uma. A caixa de tinta de cada uma, em pontos, contra uma página
de 456,1 × 648,0:

```
ps_01 .. ps_12   x de 39,4 a 428,2   y de 24,5 a 597,6
rios_01          x de 39,4 a 415,7   y de 24,5 a 590,9
tex_01           x de 39,4 a 416,6   y de 23,0 a 579,8
```

**Nada sai da folha em nenhuma das catorze**, que é o defeito que esta frente embarcou três
ciclos seguidos (conteúdo 70 mm fora da folha). E o que confirmei a olho:

* a p6 tem a série de **quatro corpos — 9, 10, 11 e 12 pt — na mesma página**, e não
  partida entre duas; a p8 e a p9 têm as quatro medidas — 20, 40, 60 e 90 mm — na mesma
  página. Era o outro defeito que só olhar apanhava;
* na p10, na corrida `Better was: 13…♘xc5 14.♘b3 ♘e6 15.♕d2 ♕f6` ampliada a 600 DPI, **os
  três cavalos e as duas damas são o mesmo desenho oco**, com as contrapunções abertas. É
  o R3, visto e não só medido;
* a p7 lista as **18** famílias, nenhuma cortada pela borda;
* a p12 (tema escuro) tem 97,3 % de tinta porque o fundo é escuro, e o texto e a moldura
  lêem-se contra ele; a p7 tem 3,1 % porque é uma lista que acaba a `y=507,8` e deixa 140 pt
  de pé branco — é o fim de uma secção, não uma página falhada;
* a cabeça corrente da página portuguesa é `Capítulo 4 — peões pendentes`, acentuada e com
  o mesmo travessão do subtítulo `Capítulo 4 — os planos das brancas` uma linha abaixo;
* **nenhuma linha de meio de parágrafo pára antes da margem direita** em nenhuma das quatro
  páginas de livro (p10, p11, p12, `rios`).

Os defeitos que vi e que continuam abertos são os que a §9 já nomeia, e vêem-se: `2.
Molduras` no pé da p2 sem um único dos seus seis espécimes, e o `g` da p4 empurrado para
cima pelo rei de g1.

### 10.6 Q5 — a vantagem é real ou só reparada?

A pergunta é a certa e a resposta honesta tem duas metades.

**O que é real.** O portão passou a ver a peça, e isso é verificável de três maneiras
independentes que não dependem umas das outras: pela camada de texto das duas páginas, pela
lista de glifos lida dos desenhos, e pelo argumento de `\cfig{...}` no `.tex` — esta
última sem fonte, sem codificação e sem compilador. As três apanham a sabotagem, para as
seis peças, com compilação real, na suíte. **Nenhuma das cinco referências tem dois
caminhos de saída**, portanto nenhuma pode apresentar um número desta espécie. Enquanto
afirmação sobre o que a ferramenta garante — *o mesmo livro sai igual pelos dois
exportadores, peça a peça* — a vantagem é defensável.

**O que é reparação e não vantagem.** Três coisas, ditas sem atenuante:

1. **O 222 do ciclo 4 não era uma vantagem menor; era uma medida vazia.** Comparava duas
   páginas com os figurinos normalizados para fora — isto é, comparava tudo menos aquilo de
   que um livro de xadrez é feito. Passar de uma medida vazia para uma medida verdadeira é
   **repor o zero**, não subir. O ciclo 6 não ganhou terreno neste portão; deixou de o
   reivindicar sem base.
2. **O «livro» tem uma página.** 43 figurinos, 198 tokens, um jogo. Paridade a esta escala
   diz que o caminho está certo, não que aguenta um livro. A §9 nº 8 já o diz e continua a
   ser o limite honesto da alegação.
3. **A vantagem é de processo, não de página.** Um leitor que ponha a nossa folha ao lado
   das cinco referências não vê a paridade entre exportadores. Vê a faixa de espaço entre
   palavras — onde hoje **perdemos para quatro das cinco** (2,13× / 0,53×, §1.4) — e vê o
   título órfão e o `g` fora da fila. Q5 pede *uma vantagem medida sobre as referências*, e
   esta é medida e é sobre uma dimensão que as referências não têm; mas é preciso dizer que
   ela não se vê na folha, e que as dimensões que se veem não melhoraram todas.

**Veredicto:** Q5 fica **defensável, com a natureza da alegação corrigida.** A frase certa
não é «compomos melhor que as referências»; é «somos o único dos seis com dois exportadores
e o único que pode provar, peça a peça e sob sabotagem, que produzem o mesmo livro». O R2
tornou essa frase verdadeira — antes dele era falsa, porque o instrumento não olhava para as
peças. Chamar-lhe *conquista* deste ciclo seria comprar outra vez o número que o crítico já
apanhou comprado duas vezes.
