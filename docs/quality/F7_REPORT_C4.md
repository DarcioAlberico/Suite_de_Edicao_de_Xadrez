# F7 — Tipografia · ciclo 4

> **Data:** 2026-09-07 · **Máquina:** a de referência (Windows 11, `.venv` do projeto)
> **Entrada:** `docs/quality/F7_CRITIQUE_C3.md` — REPROVADO, cinco portões **Q1–Q5**.
> **Estado:** Q1, Q2, Q3 e Q4 fechados com a medida do crítico. **Q5 fechado por uma das
> três candidaturas (a paridade entre exportadores) e declarado ABERTO nas outras duas**,
> com os números que faltam, abaixo.

Este ciclo teve dois autores. Um agente anterior foi interrompido por limite de taxa
**depois** de escrever o código e **antes** de escrever o relatório; o trabalho dele
estava no disco e a suíte estava verde, mas nada dizia o que estava feito. Cada item
abaixo diz **quem fez** — «ciclo 4 (a)» é o agente anterior, «ciclo 4 (b)» sou eu — e o
que eu fiz foi partir dos scripts do crítico, medir o estado real e fechar o que ainda
estava aberto.

Todo número deste documento saiu de um comando que rodei nesta máquina depois da
reconstrução final dos artefactos, e o comando está ao lado do número. Onde o alvo do
crítico não foi atingido, o texto diz isso em vez de arredondar.

---

## 0. Como reproduzir

```
.venv\Scripts\python.exe tools\typeset_proofsheet.py --png     # a folha e os 12 PNG
.venv\Scripts\python.exe tools\build_latex.py                  # o PDF do LaTeX
.venv\Scripts\python.exe tools\compare_exporters.py            # Q3 e Q5
.venv\Scripts\python.exe -m pytest tests -q                    # a suíte inteira

.venv\Scripts\python.exe tools\measure_typography.py marks      # Q1 (SVG)
.venv\Scripts\python.exe tools\measure_typography.py latexmarks # Q1 (LaTeX)
.venv\Scripts\python.exe tools\measure_typography.py inside     # Q2
.venv\Scripts\python.exe tools\measure_typography.py holes      # Q4 nº 1
.venv\Scripts\python.exe tools\measure_typography.py indent     # Q4 nº 4
.venv\Scripts\python.exe tools\measure_typography.py wordspace  # Q4 nº 5
.venv\Scripts\python.exe tools\measure_typography.py grid       # Q5 candidata 1
.venv\Scripts\python.exe tools\measure_typography.py feet       # pé de coluna
.venv\Scripts\python.exe tools\measure_typography.py bottom     # margem inferior
.venv\Scripts\python.exe tools\measure_typography.py counters   # figurino negrito
```

Os scripts do crítico em `benchmarks\reports\critique\c3\` também rodam contra os
artefactos novos; os que uso abaixo são `holes.py`, `occupancy.py`, `indent.py`,
`sizes.py`, `dash.py`, `eval.py`, `textaudit.py`, `cap.py`, `ell.py` e `register.py`.
Dois deles deixaram de medir o que mediam e digo qual e por quê na §7.

---

## 1. Q1 — marcas que não destroem peças · **FECHADO**

Feito no ciclo 4 (a): a marca passa **por baixo** das peças e só a ponta volta por cima,
contornada na cor da casa de destino. Verifiquei os três critérios do crítico, nos dois
exportadores.

| Critério do crítico | Alvo | SVG | LaTeX |
|---|---|---|---|
| contorno da peça atravessada: mesma contagem de componentes conectados | 0 partidos | **0 de 70** | **0 de 22** |
| tinta da peça de destino que sobrevive | ≥ 80 % | **93,5 %** | **83,0 %** |
| contraste da ponta contra a peça | ≥ 3:1 (ciclo 2: 1,99:1) | **3,39:1** | **3,34:1** |

```
tools\measure_typography.py marks       -> 70 hastes, 0 contornos partidos; 93.5 %; 3.39:1
tools\measure_typography.py latexmarks  -> 22 hastes, 0 contornos partidos; 83.0 %; 3.34:1
```

O contraste da ponta é ≥ 3:1 nos **seis** temas (menor: `warm`, 3,02:1). Olhei o
espécime da p5 a 2× (recorte em `setas retas`): as hastes d1–d7, g2–b7 e c1–c5 passam por
baixo do cavalo de d2, do peão de d5 e do peão de c2 com o contorno inteiro, e as pontas
sobre o cavalo de d7 e o bispo de b7 têm o contorno claro que as separa da peça.

## 2. Q2 — `inside` sem tocar nas peças · **FECHADO**

Feito no ciclo 4 (a): o rótulo de dentro procura um canto **livre** da própria casa,
medido contra a silhueta da peça; uma casa sem canto livre devolve as coordenadas para
fora, e o quarto espécime da p4 mostra isso.

```
tools\measure_typography.py inside
  posicao do especime aceita as coordenadas de dentro: True
  posicao cheia (torre em c1, dama em d1): False   (esperado False)
  rotulos desenhados: 16 -- 12345678abcdefgh
  pecas com entalhe: 0   (criterio: 0)
```

**16 rótulos inteiros, 0 peças com entalhe.** Ampliei a fileira 1 da p4 a 3×: o rótulo
`g` saiu para o canto superior direito da casa porque o rei ocupa a base, e nenhuma letra
é cortada pela aresta da fileira.

## 3. Q3 — paridade real entre exportadores · **FECHADO**

Feito no ciclo 4 (a) — os dois exportadores passaram a sair de **uma** lista de corridas
(`tools/build_latex.py::runs_to_tex`) — e estendido por mim no ciclo 4 (b) com a estrutura
em itálico e com a mobília do tabuleiro (§3.2).

```
tools\compare_exporters.py
  pagina inteira, token a token .................. 222 tokens, identicos
  legendas dos diagramas ......................... 3 legendas, identicas
  cabeca corrente ................................ iguais
  estrutura: corridas em negrito ................. SVG 93, LaTeX 93, identicos
  estrutura: corridas em italico ................. SVG 15, LaTeX 15, identicos
  a divergencia declarada: a reticencia .......... '…' vs '...'; espaco depois 0.00 / 0.00 pt
  TOTAL: 0 divergencia(s) nao declarada(s) + 1 declarada
```

Os cinco pontos que o crítico mediu no ciclo 3, um a um: espaço depois da reticência
**0,00 pt nos dois** (era 5,12 pt no LaTeX); legenda `After 21.♗xh7†.` **igual nos dois**;
travessão da legenda **igual nos dois**; **93 contra 93** corridas em negrito (era 71
contra 7); a reticência continua declarada e contada.

> **Aviso a quem rodar `cap.py`.** Aquele script imprime «bold spans: 84» do lado LaTeX e
> «64» do lado SVG, e os dois números **não** são comparáveis: ele conta *spans distintos*
> do extrator, e o escritor de PDF do lado SVG funde corridas vizinhas da mesma face num
> só span (`'10.cxd5 exd5 11.'`) enquanto o pdfTeX emite um span por token. É segmentação
> do produtor de PDF, não decisão de composição. `compare_exporters.py` compara **tokens**
> em negrito depois de normalizar — 93 contra 93, idênticos, token a token.

### 3.1 O que eu acrescentei: a estrutura em itálico

O ciclo 4 (a) comparava só o negrito. O itálico é a outra metade da estrutura — separa a
legenda e o nome de um jogador da prosa — e os dois exportadores chegam lá por caminhos
diferentes (`TimesNewRomanPS-ItalicMT` de um lado, `LMRoman9-Italic` do outro) a partir da
mesma `Run.face`. Agora é comparado: **15 contra 15, idênticos.**

### 3.2 O que eu acrescentei: a mobília do tabuleiro

`chessboard` tem `showmover=true` por omissão e o `DiagramStyle` do lado SVG deixa
`side_to_move=SideToMove.NONE`. O PDF do LaTeX do ciclo 3 imprimia, portanto, **um
quadrado preto no canto superior direito dos três diagramas** que o SVG não imprime.
Nenhuma comparação de tokens podia vê-lo — uma caixa não é um token — e eu vi ao olhar a
página. `tools/build_latex.py` passa agora `show_mover=False`; teste novo
`test_the_two_exporters_draw_the_same_board_furniture`.

## 4. Q4 — teto e blocos indivisíveis · **FECHADO (6 de 6)**

Os cinco primeiros itens vieram do ciclo 4 (a); o sexto estava **aberto** e fechei-o eu.

| nº | critério | alvo | medido |
|---|---|---|---|
| 1 | maior vão interno | ≤ 2 entrelinhas no livro, ≤ 4 no espécime | **1,91** (livro) · **3,47** (espécime) |
| 2 | título + 1º parágrafo indivisíveis | vão rígido, mesma página | **1,04 entrelinhas (4,11 mm) nas 9 seções, idêntico** |
| 3 | cabeça de partida + régua + local | ≤ 1 entrelinha entre régua e local | **0,49 entrelinhas = 1,81 mm** (ref. C: 4,0 mm; ciclo 2: 9,7 mm) |
| 4 | bloco recuado leva as continuações | 0 | **0 blocos** |
| 5 | linha justificada mais frouxa | ≤ 2,00× o espaço nominal | **1,73×** (ciclo 2: 3,00×) |
| 6 | uma série de quatro não se parte | 4 na mesma página | **as duas séries fechadas** |

```
tools\measure_typography.py holes     -> maior vao interno 3.47 entrelinhas (teto 2 / 4)
tools\measure_typography.py indent    -> blocos recuados cuja continuacao volta a margem: 0
tools\measure_typography.py wordspace -> linha mais frouxa 1.73x; linhas acima de 2,0x: 0
tools\measure_typography.py feet      -> p10/p11/p12: pes das colunas, diferenca 0.000 mm
tools\measure_typography.py bottom    -> 12 paginas, 0 com conteudo abaixo da margem
```

O ciclo 2 comprava o pé de 0,000 mm com buracos: nove das doze páginas tinham um vão
igual ou maior que 8 mm e a p8 tinha **35,6 mm = 8,2 entrelinhas**. Hoje as páginas de
livro (10–12) têm 1,91 entrelinhas de vão máximo e as folhas de espécimes 3,47, com
`MAX_GAP_SLOTS = 1` (livro) e `SPECIMEN_GAP_SLOTS = 2` a impor o teto por construção.

### 4.1 Q4 nº 6, a segunda série — o que estava aberto

A crítica escreve: *«uma fileira de espécimes que não cabe não parte a série que a seção
existe para comparar: os quatro tamanhos, na mesma página»*. O ciclo 4 (a) fechou isso
para a série **20/40/60/90 mm** das seções 8 e 9 (`Gallery(rows=(3,1), keep_together=True)`)
e o teste correspondente procura rótulos terminados em `mm`.

A seção 6 é a **outra** série de quatro — o figurino a **9, 10, 11 e 12 pt**, e a sua
própria linha de apoio diz isso. Ao olhar página a página encontrei-a partida: 9, 10 e 11
na p6 e **12 pt sozinho no topo da p7**. Exatamente o defeito do Q4 nº 6, na seção cujo
texto o anuncia, e invisível para o teste que só olha para `mm`.

Por que não cabia, em números (`flow()` com a geometria real da folha):

```
capacidade da pagina = 49 casas de grade
p6 antes: fileira de marcas 18 + secao 6 inteira 36 = 54  ->  5 casas a mais
          (o que cabia eram 46: a secao 6 sem o bloco de 12 pt)
```

O que fiz:

* **Encurtei o parágrafo-espécime** de 362 para 186 caracteres. Era 4/4/5/5 linhas nos
  quatro corpos (18 casas); é 2/2/3/3 (10 casas). A seção passou de 36 para **28 casas** e
  entra debaixo da fileira de marcas com **três casas de sobra** (46 de 49). O espécime
  continua a carregar tudo o que a seção existe para mostrar: figurinos em texto corrido
  (`13.dxc5`, `14.♘b3!`), uma corrida em negrito, uma em itálico e um símbolo de avaliação.
* **Amarrei a série**: todos os blocos da seção, do título à linha de 12 pt, levam
  `keep_with_next`, de modo que o compositor move a série inteira ou não move nada — e os
  vãos dentro dela ficam rígidos, porque `compose` torna rígido o vão depois de um bloco
  amarrado. O ciclo 4 (a) tinha a corrente só nos rótulos de tamanho, o que prendia o
  rótulo ao seu parágrafo e deixava a quebra cair **entre dois tamanhos**.
* **Teste novo** `test_the_four_type_sizes_of_the_figurine_section_stay_on_one_page`:
  exige que `9 pt`, `10 pt`, `11 pt` e `12 pt` apareçam numa única página.

Depois disso a p6 leva os quatro corpos (verificado no PNG) e a p7 começa na seção 7.

### 4.2 O efeito colateral que a mudança revelou, e o que fiz com ele

Com a seção 6 oito casas mais curta, a p7 passou a fechar com **9 casas de défice**, e o
`feather` fechou-a dando uma casa extra aos **primeiros nove** dos dezoito vãos entre as
fileiras de peças: uma lista cujo ritmo muda a meio. Vi isso no PNG.

A causa é que rigidez e amarração eram a **mesma** alavanca: um vão era rígido exatamente
quando o bloco anterior dizia `keep_with_next`. Isso serve um título — que tem de manter o
parágrafo *e* segurá-lo a uma distância fixa — e não serve uma lista de dezoito fileiras
iguais, cujos vãos têm de ficar iguais mas que não podem ser amarradas todas numa corrente:
a página tem 49 casas e a seção custa `6 + 2N`, portanto a corrente estoura na vigésima
segunda família instalada e a folha deixa de compor de todo.

Separei as duas: `typeset_page.Block.rigid_before` marca o vão **antes** do bloco como não
crescível sem o prender à página. As dezoito fileiras da seção 7 usam-no. Resultado: uma
única cadência na lista inteira e a página a acabar mais cedo — que é a troca que o próprio
`MAX_GAP_SLOTS` já defende em texto («um pé que não fecha é falta menor do que um buraco no
meio da página»).

```
tools\measure_typography.py holes   ->  p7  maior vao interno 2.16 entrelinhas (era o
                                        ritmo partido; o teto de 4 nunca foi violado)
tools\measure_typography.py feet    ->  p7  pe 509.3 pt, folga ate a margem 32.9 mm
```

O preço, declarado: a p7 acaba **32,9 mm acima da margem inferior** (48,9 mm de branco no
pé, contando a margem). É o fim de uma seção de dezoito fileiras fixas, não um buraco: o
maior vão **interno** da página é 2,16 entrelinhas. A p5 já entregava 28,1 mm pelo mesmo
motivo no ciclo 3 e o crítico não a apontou.

## 5. Q5 — uma vantagem medida · **UMA das três candidaturas fechada**

A crítica deu três candidatas e pediu uma, ganha com número.

### 5.1 Candidata escolhida: o mesmo livro nos dois exportadores · **FECHADA**

> *«o mesmo livro nos dois exportadores, indistinguível token a token e span a span, o que
> nenhuma editora do conjunto pode oferecer porque nenhuma tem dois caminhos»*

O número está na §3: **222 tokens, 3 legendas, 1 cabeça corrente, 93 corridas em negrito e
15 em itálico — 0 divergências não declaradas**, mais uma declarada (a reticência, cujo
espaço seguinte é 0,00 pt nos dois lados). E, desde este ciclo, os dois exportadores
desenham também a **mesma mobília de tabuleiro** (§3.2), que era a única diferença visível
que sobrava entre as duas páginas.

Não é empate por construção: nenhuma das cinco referências tem dois caminhos de saída, e
portanto nenhuma pode apresentar este número. É a única das três candidatas que este ciclo
ganha, e é sobre ela que assento o Q5.

**A ressalva honesta:** o «livro» é hoje **uma** página nos dois exportadores
(`livro.pdf` tem 1 página; a folha SVG tem 12, das quais 3 são essa página em três temas).
A alegação é «a mesma página-fonte, pelos dois caminhos, indistinguível». Não afirmo
«um livro inteiro» — não há um.

### 5.2 Candidata 1: grade de linha de base a 100 % / 100 % · **ABERTA**

Registo com o número, não com uma volta.

```
tools\measure_typography.py grid
  coluna esquerda: 22 linhas de base, 22 na grade de 10.406 pt, 51 casas,
                   16 tomadas por diagrama, ocupacao 63 %
  coluna direita : 15 linhas de base, 15 na grade de 10.406 pt, 51 casas,
                   32 tomadas por diagrama, ocupacao 79 %
  registo atraves da calha: 9 de 15 = 60 %   (ciclo 2: 41 %; amostra F: 100 %)

benchmarks\reports\critique\c3\occupancy.py   (o script do crítico, sem alteração)
  left:  22 baselines over 51.0 grid slots -> occupancy 43 %
  right: 15 baselines over 35.0 grid slots -> occupancy 43 %
```

Duas coisas, medidas:

1. **O registo transversal é exato.** Medindo a fase de cada linha de base da coluna
   direita contra a grade da coluna esquerda, com a tolerância de 0,4 pt que o crítico usa
   em `register.py`: erro máximo **0,0008 pt**, **100 %** das linhas dentro da tolerância,
   nas três páginas de livro. O mesmo script do crítico dá **100 %** para a amostra F e
   **0 %** para B, C e D. Isto é vitória sobre três referências e **empate com a F** — e a
   crítica diz que empate não aprova, por isso não é aqui que assento o Q5.
2. **A ocupação não chega a 100 % e não vai chegar** enquanto a página tiver diagramas. A
   medida do crítico conta linhas de base de **corpo** contra o total de casas entre a
   primeira e a última; três diagramas, três legendas em itálico, uma cabeça de partida e
   dois subtítulos ocupam casas que nunca contarão como linha de corpo. A amostra F, que
   marca 100 %, é uma página de texto corrido sem um único diagrama. Fabricar o 100 %
   exigiria tirar os diagramas da página de livro de um livro de xadrez, e isso seria
   ganhar a medida perdendo a coisa medida. **Fica aberta e declarada.**

### 5.3 Candidata 2: símbolos de avaliação como glifos únicos · **ABERTA**

```
benchmarks\reports\critique\c3\eval.py
  p6  '16.e3±'            -> U+00B1                     (glifo único)
  p10 '21.♗xh7†!+−'       -> U+2020 U+0021 U+002B U+2212 (par)
  p10 '25.♕g4+−.'         -> U+002B U+2212               (par)
```

`±` sai como glifo único (U+00B1). `∓`, `⩲` e `⩱` continuam a **não** ser compostos: o
`chess_symbols` só troca quando a face de destino tem o glifo, e Times New Roman tem
U+00B1 e não tem U+2213, U+2A71 nem U+2A72 — verificado com `pymupdf.Font.has_glyph`, não
suposto. `+−` sai como o par correto U+002B U+2212 (era U+002B com EN DASH; ver §6). Para
fechar esta candidata seria preciso desenhar os seis símbolos como glifos vetoriais da
fonte de xadrez, pelo caminho do figurino — não foi feito neste ciclo. **Aberta.**

## 6. Os itens menores da crítica

| item da crítica | estado | número, medido agora |
|---|---|---|
| duas seções numeradas 8 | fechado, ciclo 4 (a) | seções `[1,2,3,4,5,6,7,8,9]`, únicas e crescentes |
| corpo 3,40 pt na p4 | fechado, ciclo 4 (a) | menor corpo da p4: **5,71 pt**; menor da folha inteira: **5,61 pt**, na p5 (`sizes.py`) |
| legenda «90 mm» a 9,3 mm do seu tabuleiro | fechado, ciclo 4 (a) | pior desvio de **8** legendas: **0,96 pt = 0,34 mm** |
| `+–` com EN DASH onde existe U+2212 | fechado, ciclo 4 (a) | `+−` = U+002B U+2212 (`eval.py`); as **19** EN DASH da folha são só nomes emparelhados (`Vitiugov – Bologan` ×4, `Sandro Mareco – Christian Toth` ×3, `Family One – d4` ×3), roques (`0–0` ×3) e resultados (`1–0` ×3) — nenhuma num símbolo de avaliação (`dash.py`, enumeradas uma a uma) |
| continuações de sub-variante desrecuadas | fechado, ciclo 4 (a) | **0** blocos recuados cuja continuação volta à margem (`indent`) |
| moldura do tema escuro a 1,14:1 | fechado, ciclo 4 (a) | **14,13:1** — moldura `#EDEDEA` sobre página `#1B1F23`, medido no pixel da p12 |
| figurino negrito engordado por traçado | fechado com ressalva, ciclo 4 (a) | contrapunção do bispo **0,73** (piso 0,70); a dama fica em **0,56** e é declarada, não arredondada |
| ferramenta `feet` só reportava três páginas | fechado, ciclo 4 (a) | reporta as **12** |
| substituição `T1/lmss/m/up` não declarada | fechado, ciclo 4 (a) | `build_latex.py`: «substituicoes de fonte nao declaradas: **0**» |

Auditoria de texto (`textaudit.py`): 0 apóstrofos retos, 0 aspas retas, 0 hífens ASCII
usados como travessão, 0 reticências de três pontos, 0 espaços duplos, 0 espaços antes de
pontuação. As seis ocorrências que o script marca como «plus-minus escrito como `+−`» são
o par U+002B U+2212 — correto para Times, e o assunto da §5.3.

## 7. Dois scripts do crítico que deixaram de medir o que mediam

Digo-o porque quem re-verificar vai rodá-los.

* **`dark2.py`** amostra a moldura numa linha fixa, `y = y0 − 0,3 pt` com `y0 = 54,8`. O
  quadro real da p12 começa em `y0 = 56,0`, por isso o script lê o fundo da página e
  imprime «frame = ground, CR 1.00» para as três páginas de livro — inclusive para a
  hachurada, cuja moldura é preta sobre branco. Medindo a mesma linha em `y0 = 56,0`:
  hachurada **21,00:1**, cinza **21,00:1**, escura **14,13:1**.
* **`register.py`** lê `benchmarks/reports/blind2/amostra_*.png` a 200 DPI; não há entrada
  para a nossa folha. Aplicá-lo à nossa página exige recalibrar o passo (ele procura o
  passo mais fino que ainda dá índices únicos e encontra **metade** da nossa entrelinha) e
  a origem. Por isso a §5.2 mede a fase diretamente contra a grade de 10,406 pt em vez de
  citar um número saído do script fora do seu domínio.

## 8. Olhei para todas as páginas

O ciclo 2 entregou uma página 37 % branca com um título a 27,8 mm do seu parágrafo e não
reparou; o ciclo 1 entregou conteúdo 70 mm fora da folha. Por isso, depois da reconstrução
final, abri **as doze páginas** do PNG a 200 DPI, uma a uma, mais a página do LaTeX, mais
dois recortes ampliados (a fileira 1 do espécime `inside` da p4 a 3× e as setas da p5 a
2×).

O que a inspeção encontrou, e que nenhuma medida tinha apanhado: a série dos quatro corpos
partida entre a p6 e a p7 (§4.1), o ritmo partido da lista de dezoito famílias da p7
(§4.2) e o quadrado de «quem joga» nos diagramas do LaTeX (§3.2). Os três estão fechados.

Para o registo, a tinta por página depois da reconstrução (`ink = pixels < 250`), com a
última linha impressa:

```
p 1 24,0 %   p 2 23,9 %   p 3 19,6 %   p 4 16,5 %   p 5 15,0 %   p 6 14,9 %
p 7  4,5 %   p 8 18,2 %   p 9 11,0 %   p10 11,7 %   p11 16,6 %   p12 100 % (tema escuro)
```

A p7 é a lista de dezoito fileiras de figurinos numa folha branca — 4,5 % de tinta é o que
uma lista dessas pesa, não um sinal de página vazia; a última fileira imprime em y = 1412
de 1800.

## 9. O teste instável

`test_the_baselines_of_the_two_columns_register` foi reportado como dependente da ordem
sob `pytest-randomly`. **Não consegui reproduzir a falha** e digo isso em vez de alegar uma
correção que não posso demonstrar: passou nas execuções da suíte inteira desta sessão
(§10), com a ordem aleatória por omissão e portanto com sementes diferentes, e passou
também na execução de `tests/unit/typeset` com `-p no:randomly`.

O que fiz mesmo assim, contra a hipótese que me foi dada (um cache de fonte a nível de
módulo): a folha é construída **uma vez** por sessão e, sob ordem aleatória, *qual* teste a
pede primeiro muda a cada execução — e quatro caches de vida-do-processo estão no caminho
da composição (`typeset_page.serif_family`, `typeset_page._patched_faces`,
`typeset_page._pymupdf_font`, `fonts._open_ttfont`). A fixture `proofsheet` limpa os quatro
antes de compor (`_cold_font_caches`), de modo que a folha passa a ser função só da fonte
do documento, seja o que for que tenha corrido antes. Custa cerca de um segundo.

Se a instabilidade voltar, o teste imprime as linhas fora da grade e a sua ordenada; não
falha em silêncio.

## 10. A suíte

Duas execuções completas, com a ordem aleatória por omissão e portanto com sementes
diferentes, depois de toda a mudança deste ciclo:

```
.venv\Scripts\python.exe -m pytest tests -q
  execucao 1:  2912 passed, 1 skipped in 601.70s (0:10:01)
  execucao 2:  2912 passed, 1 skipped in 596.79s (0:09:56)
```

O único `skipped` é o de sempre: `test_fonts.py::…woff2`, que pede o compressor Brotli e
diz porquê.

Base do ciclo anterior: 2910 passed, 1 skipped, 0 failed. Acrescentei dois testes —
`test_the_four_type_sizes_of_the_figurine_section_stay_on_one_page` (Q4 nº 6, §4.1) e
`test_the_two_exporters_draw_the_same_board_furniture` (§3.2) — e 2910 + 2 = **2912**.
Nada regrediu.

```
.venv\Scripts\python.exe -m pytest tests/unit/typeset -q -p no:randomly
  263 passed, 1 skipped in 220.63s (0:03:40)
```

Uma nota de precisão, para não haver alegação maior do que a medição: depois destas três
execuções corrigi **dois textos de documentação** (a docstring de `Block.rigid_before` e o
número correspondente na §4.2 deste relatório) — nenhuma linha executável. A seguir a essa
correção rodei os quatro testes diretamente afetados
(`…four_type_sizes…`, `…board_furniture…`, `…gap_passes_the_ceiling`,
`…baselines_of_the_two_columns_register`): **4 passed**.

## 11. O que continua em aberto, sem rodeios

1. **Q5, candidata 1** — ocupação 43 %/43 % pela medida do crítico, 63 %/79 % descontando
   as casas tomadas por diagrama. O registo transversal é 100 % com erro máximo de
   0,0008 pt, o que empata com a amostra F. §5.2.
2. **Q5, candidata 2** — `∓`, `⩲` e `⩱` continuam sem sair, e `+−` sai como par. §5.3.
3. **A contrapunção da dama em negrito**: 0,56 contra o piso de 0,70 do crítico. Só o
   bispo — o glifo que a crítica nomeou — está acima do piso.
4. **O «livro» dos dois exportadores é uma página.** §5.1.
5. **A p7 acaba 32,9 mm acima da margem** — o preço declarado do Q4 nº 6. §4.2.
