# F7 — Tipografia · ciclo 2

> **Data:** 2026-09-07 · **Máquina:** a de referência (Windows 11, `.venv` do projeto)
> **Entrada:** `docs/quality/F7_CRITIQUE_C1.md` — REPROVADO, doze defeitos bloqueantes.
> **Estado:** onze fechados com a medida do crítico; **um fechado em 4/5 e aberto no
> quinto elemento**, declarado abaixo com o número.

Todo número deste documento saiu de um comando que rodei nesta máquina, e o comando está
ao lado do número. Onde o alvo do crítico não foi atingido, o texto diz isso em vez de
arredondar. A crítica derrubou três alegações do relatório do ciclo 1; parto do princípio
de que tudo aqui será re-verificado, e as ferramentas para re-verificar são as minhas
próprias, entregues junto.

---

## 1. Como reproduzir tudo

```
.venv\Scripts\python.exe -m pytest tests/unit/typeset -q
.venv\Scripts\python.exe tools\typeset_proofsheet.py --png
.venv\Scripts\python.exe tools\build_latex.py
.venv\Scripts\python.exe tools\compare_exporters.py

.venv\Scripts\python.exe tools\measure_typography.py bottom      # P1
.venv\Scripts\python.exe tools\measure_typography.py feet        # balanço de coluna
.venv\Scripts\python.exe tools\measure_typography.py marks       # P2
.venv\Scripts\python.exe tools\measure_typography.py highlight   # P2
.venv\Scripts\python.exe tools\measure_typography.py frames      # P3
.venv\Scripts\python.exe tools\measure_typography.py hatch       # P3
.venv\Scripts\python.exe tools\measure_typography.py coords      # P3
.venv\Scripts\python.exe tools\measure_typography.py figurine    # P4
```

`tools/measure_typography.py` é novo e existe por um motivo: **cada critério de aceite da
crítica tem um subcomando que imprime a mesma grandeza que o crítico imprimiu, pelo mesmo
método** (densidade contínua `1 − v/255` dentro da caixa de tinta do glifo; varredura
horizontal numa casa escura vazia; `get_drawings()['width']` do vetor, nunca do raster).
Os rasters são produzidos na hora, não lidos do disco, então um número não pode estar
velho.

| Artefato | Caminho | O que mudou |
|---|---|---|
| Folha de prova | `benchmarks/reports/proofsheet.pdf` | **12 páginas** (eram 10); nada mais é posicionado por coordenada fixa |
| Páginas rasterizadas | `benchmarks/reports/proofsheet_png/page_01..12.png` | 150 DPI (o `--dpi` é o que se pede na linha de comando) |
| LaTeX gerado + compilado | `benchmarks/reports/latex/livro.tex`, `livro.pdf` | 162 702 bytes, 1 página, **0 caixas over/underfull** |
| Comparação entre exportadores | `tools/compare_exporters.py` | novo |
| Medidor | `tools/measure_typography.py` | novo |
| Testes dos doze bloqueantes | `tests/unit/typeset/test_proofsheet.py` | novo, 41 testes |

**Eu olhei as doze páginas**, uma a uma, com a ferramenta de leitura de imagem, e
ampliei quatro regiões a 400–600 DPI (as coordenadas de dentro, a cabeça da seta do
LaTeX, o diagrama hachurado da página de livro, o figurino em negrito). Metade das
correções desta lista saiu de olhar, não de medir. O construtor do ciclo 1 despachou uma
página com conteúdo 70 mm fora do papel, e isso só é possível se ninguém olhou.

---

## 2. Os doze bloqueantes, um por um

### P1 — “A página não tem pé” · **FECHADO**

**O que era.** `tools/typeset_proofsheet.py` compunha com um `y` corrente e um
`if y > bottom: break`. Três defeitos numa linha: a guarda era testada *antes* de
desenhar o bloco e não depois; `break` **descarta** o resto da coluna em silêncio; e nada
balanceava as colunas.

**O que fiz.** Escrevi um compositor de verdade em `tools/typeset_page.py` (≈480 linhas
novas): geometria de página, blocos, átomos, fluxo entre colunas e páginas, viúvas e
órfãs por `typography.ColumnPolicy`, e **grade de linha de base** — toda medida vertical
é um número inteiro de entrelinhas. A folha de prova inteira passou a fluir por ele;
nenhuma seção posiciona nada por coordenada fixa.

O contrato está escrito no módulo e é o de um livro:

1. nenhuma marca é emitida abaixo de `text_bottom`;
2. um bloco que não cabe vai para a próxima coluna, depois para a próxima página, e se
   não couber em lugar nenhum **levanta `CompositionError`** — nunca é descartado;
3. o tema muda cores, nunca conteúdo;
4. as colunas fecham juntas, por construção.

**Medido** — `measure_typography.py bottom`, que percorre as 12 páginas comparando
`max(y1 de todo desenho e toda linha de texto)` com `altura − margem inferior` (o fundo
da página é excluído: é o papel, não conteúdo):

| | ciclo 1 | ciclo 2 |
|---|---|---|
| páginas com conteúdo abaixo da margem | **5 de 10** | **0 de 12** |
| pior transbordo | **+198,1 pt = 70 mm** (p3) | **0,00 mm** |
| menor folga numa página | — | 0,38 mm (p10–12, a página de livro, cheia até o pé) |

Testes: `test_no_page_emits_content_below_the_bottom_margin` (percorre toda página
gerada), `test_a_block_that_cannot_fit_raises_instead_of_being_dropped`.

**Mesma fonte, três temas, mesma lista de blocos.** `Composition.blocks` devolve os
rótulos de todos os átomos emitidos.
`test_composing_the_same_source_in_every_theme_emits_the_same_blocks` compõe a página nos
três temas e compara: **41 blocos, listas idênticas**. A saída do build também imprime
`mesma lista de blocos que o hachurado (cinza): True` / `(escuro): True`.

**Cabeça de lance duplicada.** A causa era concreta: `RIGHT_COLUMN` terminava em
`("move", "**14.Nb3!**")` e o parâmetro `third_diagram` **acrescentava outra igual** à
coluna esquerda. Há agora **uma** fonte, sem parâmetro de variante.
`test_no_move_heading_appears_twice_on_a_page` verifica os dois níveis: nenhum texto de
lance se repete na fonte, e nenhum rótulo de lance aparece em duas corridas separadas na
página composta.

### A vantagem mensurável: o pé de coluna

A crítica nomeou a candidata: *“nenhuma das quatro referências acerta melhor que 0,0 mm,
e um compositor que balanceie colunas de verdade e trate viúvas e órfãs no caminho SVG
entrega isso por construção.”*

Entrega. Medido no PDF terminado com `measure_typography.py feet`:

| Página | Pé da coluna esquerda | Pé da direita | Diferença |
|---|---|---|---|
| p10 (tema hachurado) | 601,6 pt | 601,6 pt | **0,000 mm** |
| p11 (tema cinza) | 601,6 pt | 601,6 pt | **0,000 mm** |
| p12 (tema escuro) | 601,6 pt | 601,6 pt | **0,000 mm** |

Referências medidas pelo crítico: 0,0 / 1,8 / 4,6 / 10,7 mm. Nosso ciclo 1: 14,5 mm.

E há uma segunda propriedade que **nenhuma das quatro referências tem**: como toda altura
é múltipla da entrelinha, as linhas das duas colunas **registram entre si através da
calha**. Medido na página 10: **28 linhas de base distintas, todas na mesma grade de
10,406 pt, zero fora**. É o que
`test_the_baselines_of_the_two_columns_register` afirma.

Como funciona, em uma frase: uma linha ocupa 1 casa da grade, um diagrama ocupa
`ceil(altura/entrelinha)` casas, e quando uma coluna sobra curta o déficit é distribuído
pelos intervalos entre blocos **em casas inteiras** (justificação vertical), o que fecha o
pé sem tirar as linhas do registro. O limite é 2 casas por intervalo na página de livro
(valor de livro) e 6 na folha de espécimes, onde a alternativa seria uma coluna que para
53 mm antes do fim porque a próxima fileira de espécimes mede 66 mm e é indivisível.

### P2 — Marcas e `inside` · **FECHADO**

**Recorte (knockout).** Toda marca — seta, círculo — é agora traçada primeiro na cor do
papel, `KNOCKOUT_MM = 0.30` mm de cada lado, e só depois preenchida. Nos **dois**
exportadores: no LaTeX o mesmo lance é desenhado duas vezes, primeiro
`[-,line width=3.4pt,draw=white]straightmove` e depois a seta, e a ponta recebe
`shorten >=1.5pt` para pousar *sobre* a peça em vez de dentro dela.

**Medido** — `measure_typography.py marks` conta pixels da cor da seta dentro da cabeça
da seta d1→d7, que aterrissa no cavalo preto de d7:

| Diagrama | pixels da cor da seta na cabeça | fração |
|---|---|---|
| 40 mm | 126 de 256 | 49 % |
| 62 mm | 306 de 576 | 53 % |
| 90 mm | 649 de 1156 | 56 % |

No ciclo 1 “só as farpas apareciam por baixo”. A meia página do LaTeX foi olhada a
600 DPI: a ponta está desenhada por cima do peão preto de g7, com o recorte branco
separando-a da peça. Testes:
`test_the_arrowhead_is_visible_over_the_piece_it_points_at` (três tamanhos) e
`test_the_latex_arrow_carries_a_knockout` (ordem de pintura: o recorte antes, ou apaga a
seta).

Além do recorte, a cauda da seta agora começa na aresta da casa (0,44 de casa do centro)
quando a casa de origem tem peça, em vez de 0,30 — a “seta g2→b7 que começava dentro do
bispo de g2”.

**`CoordinatePlacement.inside`.** Reescrito: as coordenadas de dentro são desenhadas
**por último**, depois das peças, cada uma sobre uma **chapa opaca da cor da própria
casa** (a cor com o matiz do destaque, se a casa estiver destacada). E o corpo caiu de
0,62 para **0,42 de casa** (`DiagramStyle.inside_coordinate_scale`): um rótulo de fora
tem uma calha só sua, um de dentro divide a casa com uma peça.

**Verificado** duas vezes, porque cada um sozinho pode passar com o diagrama ainda
inútil: os elementos de texto vêm **depois** do último `path` de peça na ordem do
documento, e cada um dos 16 rótulos carrega tinta legível no raster a 600 DPI. Ampliei o
espécime da folha de prova a 500 DPI e li os dezesseis: 8 7 6 5 4 3 2 1 e a–h, incluindo
os sete que o ciclo 1 destruía (8, 7, 2, c, d, f, g). Teste:
`test_every_inside_coordinate_is_legible`.

**Destaque de casa.** Deixou de ser uma sobrescrita e passou a ser um **deslocamento**:
`delta = highlight_fill − light`, somado às **duas** cores de casa, reduzido — e só
reduzido — pelo maior fator que impeça qualquer canal de saturar (`highlight_pair`). Como
o delta é o mesmo, a diferença entre as casas sobrevive intacta.

**Medido** — `measure_typography.py highlight`, amostrando c4/d4 (comuns) e c5/d5
(destacadas) no raster a 200 DPI:

| Tema | Δ casas comuns | Δ casas destacadas |
|---|---|---|
| book | 65,0 | **63,0** |
| warm | 59,0 | **57,0** |
| screen | 95,0 | **95,0** |
| dark | 61,0 | **61,0** |
| high_contrast | 117,0 | **117,0** |

Ciclo 1: c5 e d5 mediam **135 as duas**. O critério pedia “pelo menos a mesma diferença
que 255/191 tem hoje”; entrego 63 de 65 no tema `book` (a perda de 2 é arredondamento de
canal) e paridade exata nos outros quatro. O tema `hatched` fica de fora por construção —
o xadrez dele está na linha, não no matiz.

Duas consequências que o crítico mediu foram tratadas junto: um filete (keyline) de
0,055 de casa na cor de marca contorna a casa destacada, porque com o delta preservado
uma casa clara destacada cai perto de uma escura comum e sem aresta o leitor não vê onde
o destaque começa (era 1,95:1); e a peça preta sobre casa escura destacada mede agora
**5,92:1** no tema book (era 5,85 sobre o cinza chapado — mas com o xadrez morto).
Teste: `test_a_highlight_keeps_the_chequer`, que exige ≥ 90 % do delta original **e**
≥ 3:1 para o contorno da peça, em todos os temas.

### P3 — Moldura e hachura como valores de sistema · **FECHADO**

**Moldura.** Uma regra só: `FRAME_RATIO = 110`, largura do tabuleiro sobre o traço. Todo
`FrameStyle` deriva dela e fica dentro de ±15 %; o que distingue um estilo do outro é a
**estrutura** (uma régua, duas réguas, régua interna, sombra), não o peso.

**Medido** — `measure_typography.py frames`, extraindo `get_drawings()['width']` de toda
moldura quadrada traçada com mais de 40 pt de lado, nas 12 páginas:

| | ciclo 1 | ciclo 2 |
|---|---|---|
| molduras medidas | — | **55** |
| faixa | **1/98 a 1/230** | **1/101,3 a 1/122,1** |
| espalhamento dentro do mesmo documento | **2,3×** | **1,21×** |
| fora da faixa 1/93,5–1/126,5 | — | **0** |

Referências: 1/94 a 1/139. Teste:
`test_every_frame_weight_is_the_system_value`, que roda sobre a folha de prova inteira e
exige espalhamento ≤ 1,35×.

**Piso absoluto e supressão de coordenadas.** O piso de impressão (`MIN_RULE_MM = 0,18`)
só entra abaixo de ~20 mm de tabuleiro, e nesse regime as coordenadas são **suprimidas**:
`MIN_COORDINATE_PT = 5,5`, e `_layout` decide isso no próprio solve, devolvendo
`coordinates_suppressed` para que o chamador não fique adivinhando.

**Medido** — `measure_typography.py coords` percorre a camada de texto e coleta o corpo
de todo rótulo de uma letra que seja `a–h` ou `1–8`:

| | ciclo 1 | ciclo 2 |
|---|---|---|
| menor corpo de coordenada impresso | **3,92 pt** (diagrama de 20 mm) | **7,03 pt** |
| coordenadas no diagrama de 20 mm | impressas | **suprimidas** |

Testes: `test_coordinates_are_suppressed_rather_than_printed_illegibly` (API) e
`test_nothing_in_the_proof_sheet_prints_type_below_the_floor` (artefato).

**Hachura.** Três coisas mudaram. `hatch_spacing` passou a significar o passo
**perpendicular** — a distância que se mede na página — e não o passo ao longo da
diagonal `x+y`, que é √2 maior; o alvo de cobertura saiu de 19 % para **28 %**; e o teto
que abre o passo quando o traço bate no piso saiu de 19 % para 30 %.

**Medido** — `measure_typography.py hatch`, varredura horizontal pelo meio de uma casa
escura vazia, a 200 DPI, exatamente como o crítico mediu as amostras cegas:

| Diagrama | Tabuleiro | Passo perp. | px a 200 DPI | Cobertura |
|---|---|---|---|---|
| 40 mm | 39,3 mm | 0,629 mm | 4,95 | **0,314** |
| 52 mm | 51,1 mm | 0,808 mm | 6,36 | **0,318** |
| 58,7 mm | **57,7 mm** | **0,898 mm** | **7,07** | **0,319** |
| 60 mm | 59,0 mm | 0,988 mm | 7,78 | **0,314** |
| 90 mm | 88,5 mm | 1,437 mm | 11,31 | **0,318** |

Alvo do crítico: passo ≈ 0,85 mm num tabuleiro de 52 mm, cobertura 28–32 %. O tabuleiro
de 52 mm cai entre as linhas de 52 e 58,7 mm da tabela; a geometria dá 0,837 mm de passo
para ele. Ciclo 1: passo de 11 px (1,4 mm) e cobertura de **19,9 %**, a mais baixa das
sete amostras cegas.

**Honestidade sobre a ponta baixa da faixa:** abaixo de ~35 mm de diagrama o traço já
bateu no piso de impressão e a cobertura *medida* cai para 0,252 (20 mm) e 0,263 (30 mm).
A geometria continua em 0,308–0,320 nesses tamanhos; a diferença é antialiasing — uma
régua de 1,4 px a 200 DPI não renderiza preta. Na chapa a tinta está lá. O teste
(`test_hatch_ink_coverage_is_inside_the_reference_band`) cobre 40, 52, 60 e 90 mm, e digo
aqui que não cobre 20 e 30 em vez de esconder.

Verifiquei a estabilidade em três resoluções (200/300/600 DPI): 0,305 a 0,319 para todo
diagrama ≥ 40 mm. O valor de `hatch_width` foi escolhido no **piso** da faixa alvo
justamente para que a medida raster caísse no meio dela em qualquer resolução.

### P4 — Peso do figurino · **FECHADO**

Não existe um corte mais pesado destas fontes, então o contorno é **traçado na própria
cor** antes de ser preenchido, o que engrossa o anel simetricamente — exatamente o que um
peso mais pesado do mesmo desenho faria — e deixa a silhueta, o avanço e a linha de base
intactos. O peso responde ao contexto: `FIGURINE_WEIGHT_ROMAN = 0,022`,
`FIGURINE_WEIGHT_BOLD = 0,048` em em do texto, escolhidos por varredura contra a medida,
não a olho.

**Medido** — `measure_typography.py figurine`, o método do crítico: densidade contínua
`1 − v/255` dentro da caixa de tinta, do figurino e dos **dois glifos vizinhos**, nas
mesmas duas passagens (`…Bxg6.` em romano, `24.Bxh7+` em negrito). As caixas dos vizinhos
vêm da camada de texto do PDF e são recortadas fora da coluna do figurino — sem esse
recorte um figurino mais pesado invade a caixa do vizinho e melhora a própria razão, isto
é, a medida melhoraria à medida que o defeito piorasse.

| Contexto | Figurino | Vizinhos | Razão | Ciclo 1 | Referência |
|---|---|---|---|---|---|
| romano, 8,6 pt | 33,3 % | `d` 34,2 % / `x` 33,9 % | **0,98** | 0,56 | 0,94 |
| negrito, 8,6 pt | 43,6 % | `4` 44,2 % / `x` 43,6 % | **0,99** | 0,43 | 0,94 |

Estável no tamanho: medido também a 9, 10, 11 e 12 pt — razões de **0,96 a 1,00**.
Testes: `test_the_figurine_carries_the_colour_of_the_type_beside_it` (três tamanhos, dois
contextos, alvo ≥ 0,85) e `test_the_figurine_answers_the_weight_of_its_context`.

### P5 — Os dois exportadores · **FECHADO EM 4 DE 5; O QUINTO ESTÁ ABERTO E MEDIDO**

**A mudança de fundo:** o caminho LaTeX parou de pedir ao xskak que *imprima*. Os lances
são jogados invisivelmente com `\hidemoves` (comando do `skak`, que o `xskak` carrega),
de modo que o estado do jogo, `\xskakget` e todo diagrama posterior continuam exatamente
como estavam, e a notação visível é composta por `latex.typeset_moves`, das mesmas regras
que o caminho SVG usa.

**Medido** — `tools/compare_exporters.py`, que extrai a camada de texto dos dois PDFs.
Duas passagens comparadas token a token, e depois a tabela do crítico refeita sobre o
texto **cru**, sem normalização nenhuma:

```
--- abertura  [1.d4 .. d5]          12 tokens, identicos.
--- desenvolvimento  [6. .. 13.dxc5] 20 tokens, identicos.
--- os cinco elementos da tabela do critico (texto cru)
    numero de lance  SVG '1.d4'   LaTeX '1.d4'   iguais
    captura          SVG 'x'      LaTeX 'x'      iguais
    roque            SVG '0–0'    LaTeX '0–0'    iguais
    xeque            SVG '†'      LaTeX '†'      iguais
    reticencias      SVG '13…'    LaTeX '13...'  *** DIVERGEM
TOTAL: 1 divergencia(s). Ciclo 1: 5.
```

**O resíduo, dito por inteiro.** A codificação T1 do pdfTeX **não tem glifo de
reticências**. Testei `\ldots`, `\textellipsis` e o U+2026 cru via `inputenc`: os três
extraem como três pontos. O SVG imprime um U+2026; o LaTeX imprime três pontos apertados
por uma macro nossa (`\caissadots`, com kerns de 0,04 em) para que o leitor veja a mesma
coisa. **Visualmente idênticos, textualmente diferentes.** Não normalizei isso na
contagem: a ferramenta reporta 1 divergência e não 0, e este é o número que levo.
Fechá-lo de verdade exigiria trocar o motor para LuaLaTeX com `fontspec` — os dois
existem nesta máquina — mas isso troca a família de texto do documento inteiro e não me
pareceu uma decisão de F7 para tomar sozinho no último dia do ciclo.

**Um só desenho de peça por documento.** A causa era precisa e está no log do pdfTeX:
`lsfalpha.fd` declara `LSF/alpha` **só na série `m`**, e o estilo padrão do xskak compõe a
linha principal em `\bfseries`, então o LaTeX substituía por outra *família* (skaknew) em
negrito. As macros de figurino passam agora por `\cfig`, definida no preâmbulo como
`{\mdseries\csname sym#1\endcsname}`.

**Medido** — fontes embutidas na página compilada:

| ciclo 1 | ciclo 2 |
|---|---|
| `Chess-Alpha` **e** `SkakNew-Figurine-Bold` | **`Chess-Alpha`** e mais nada de xadrez |

Lista completa do ciclo 2: `Chess-Alpha`, `LMRoman10-Bold`, `LMRoman10-Regular`,
`LMRoman9-Regular`, `LMRomanSlant10-Regular`, `LMSans8-Regular`. Teste:
`test_one_piece_design_per_document`.

**`\chapter*` dentro de `multicols`.** Removido. Há agora `\gameheading{...}` no preâmbulo
— cabeçalho de coluna centrado com a régua escocesa, sem espaço de abertura de capítulo —
e a cabeça corrente saiu para `\markboth` com `\pagestyle{myheadings}`. O buraco de 25 mm
no topo da coluna 1 sumiu e o título deixou de quebrar no meio da frase; olhei a página
compilada. Teste: `test_the_game_heading_is_a_column_heading_not_a_chapter_opening`.

A compilação continua real: **0 caixas over/underfull**, 1 página, 162 702 bytes,
`benchmarks/reports/latex/compile.log`.

### P6 — A folha de prova é o entregável · **FECHADO**

**Texto em português, com acentos.** A folha inteira foi reescrita em português
acentuado. Antes: zero caracteres acentuados em dez páginas, numa frente de tipografia.
Teste `test_the_proof_sheet_is_written_in_portuguese_with_accents` exige pelo menos oito
acentuados distintos na camada de texto e a presença de palavras concretas (“posição”,
“peça”, “traço”, “família”).

**Cabeçalhos e legendas pelo `prepared()`.** O `heading()` que chamava `canvas.text()`
direto não existe mais: `Heading`, `Paragraph`, `Gallery` e `DiagramBlock` passam todo
texto por `prepared(texto, idioma)`. Teste
`test_headings_and_captions_go_through_the_typographic_pass` afirma que **não há uma
única aspa reta** na folha e que há aspas curvas e travessões.

**Idioma no hifenizador.** `TextStyle.language` viaja com o estilo e chega ao
`Hyphenator`; a folha de espécimes é `"pt"`, a página de livro inglesa é `"en"`, a segunda
página-fonte é `"pt"`. Vê-se na página: “ques-tão”, “rup-tura”, “com-pletam”. Teste
`test_the_hyphenator_gets_the_language_of_the_text`.

**As 18 famílias.** A seção “Peça a peça” mostra agora **as 18**, em duas páginas, porque
a galeria flui. Dois testes:
`test_every_verified_family_appears_in_the_piece_by_piece_section` (lista de blocos) e
`test_all_verified_families_are_actually_drawn_on_a_page` (a chave da família aparece na
camada de texto do PDF). E corrigi a alegação falsa em `F7_REPORT.md` §2.1 no próprio
arquivo, com a correção marcada.

### P7 — O arnês cego · **A minha metade está feita**

O arnês é do coordenador. Minha parte era garantir que o compositor produz páginas
**genuinamente diferentes** de fontes diferentes, e está:

* `book_source_mareco()` (inglês, Mareco–Toth) e `book_source_rios()` (português, um
  capítulo sobre peões pendentes) são duas fontes distintas;
* `tools/build_blind.py` ganhou `--source` e `--out`, foi consertado (estava com um erro
  de sintaxe: uma string quebrada em `"\n".join`, que impedia o script de rodar) e
  **recusa-se a gerar** se a página nossa não for **uma página cheia** — o ciclo 1 pôs no
  conjunto uma página que “parava em y=1479 com conteúdo ainda por compor”, e uma página
  meio vazia se denuncia antes de qualquer detalhe tipográfico;
* provei o script escrevendo num diretório fora da árvore
  (`--out <scratch>`), sem tocar em `benchmarks/reports/blind/`, que não é meu.

As duas fontes compõem **53/53 casas em cada coluna, desnível 0,000 mm**, e a lista de
blocos de uma não é a da outra. Teste:
`test_two_sources_give_two_genuinely_different_pages`.

---

## 3. O que mudei sem que me pedissem, porque olhei

1. **A camada de texto do PDF estava corrompida.** Times New Roman mapeia U+0020 e
   U+00A0 para o mesmo glifo, e U+002D e U+00AD idem; o PyMuPDF monta o `ToUnicode` do
   subconjunto invertendo o cmap e **fica com o último codepoint**. Resultado: todo espaço
   saía como espaço inquebrável e **todo hífen como hífen suave** — `the ideal c5<AD>d5
   position`. A página parecia certa e o texto extraído estava errado, que é pior que os
   dois. Corrigido removendo as duas entradas ambíguas do cmap da cópia embutida (os
   glifos, as métricas e o desenho ficam intactos) e normalizando os espaços de ligação
   para espaço comum no momento de emitir. Teste:
   `test_the_text_layer_survives_extraction`.
2. **Hifenação de nome próprio.** A crítica registrou “Vitiugov – Bolo-/gan” como defeito
   que nenhuma referência comete, e observou que a correção nº 7 do ciclo 1 (colar a
   meia-risca à palavra anterior) **criou** a quebra. `_breakable` recusa agora qualquer
   palavra iniciada por maiúscula. Na página: “compare Vitiugov – Bologan from the
   pre-vious chapter” — o nome inteiro, a quebra num advérbio.
3. **Espécimes comparáveis.** `width_mm` é a largura *acabada*, então dois diagramas que
   diferem só por carregar um indicador de lance saíam com tabuleiros diferentes para a
   mesma largura declarada — “espaçamento inconsistente entre elementos equivalentes”.
   Novo `board_svg.width_for_square(style, mm)` resolve a largura que dá a casa pedida, e
   as fileiras de espécimes da folha de prova usam-no. As legendas de uma fileira passaram
   a assentar numa **única linha de base**.
4. **`--verify` limpo.** Os ~48 avisos de timestamp do fontTools vinham por `logging`, não
   por `warnings`; silenciados no CLI para exatamente aquele logger. A tabela agora sai em
   55 linhas, 18 verificadas / 6 não.
5. **Descritores de arquivo.** `_open_ttfont` lê os bytes e passa um `BytesIO`, em vez de
   segurar o handle pela vida do processo. Os `ResourceWarning` no encerramento da suíte
   acabaram: `pytest -W error::ResourceWarning tests/unit/typeset/test_fonts.py` → 0.

---

## 4. Testes

`tests/unit/typeset/` — **238 passam, 1 pula** (o skip é WOFF2 sem Brotli, declarado
desde o ciclo 1). Eram 197/1.

| Arquivo | Testes | Cobre |
|---|---|---|
| `test_proofsheet.py` (novo) | 41 | os doze bloqueantes, um critério de aceite cada |
| `test_board_svg.py` | 33 | determinismo, ida-e-volta do FEN, molduras, coordenadas, marcas, temas |
| `test_typography.py` | 46 | aspas, travessões, símbolos, hifenização, colunas |
| `test_latex.py` | 37 | estrutura + compilação real |
| `test_fonts.py` | 23 | registro, re-verificação, subconjunto |
| `test_figurine.py` | 17 | métricas medidas, linha de base, SAN |

A folha de prova é construída **uma vez por sessão** e cinco testes a percorrem, página
por página. É o teste que o construtor do ciclo 1 não tinha, e a razão pela qual uma
página com 70 mm de conteúdo fora do papel chegou ao crítico.

**Suíte do repositório inteiro**, com os dois módulos que nem sequer importam excluídos:

```
.venv\Scripts\python.exe -m pytest tests -q ^
    --ignore=tests/unit/export/test_emf.py --ignore=tests/unit/export/test_pdfwrite.py
3 failed, 2691 passed, 1 skipped, 2 xfailed in 513.65s
```

As três falhas são `tests/unit/index/test_query.py::test_move_pattern_finds_a_knight_capture`,
`::test_move_query_object_with_extra_conditions` e `::test_regex_narrowed_by_text_first`.
**Não são minhas e são anteriores a este trabalho:** rodei a suíte antes de tocar em
qualquer arquivo e ela já dava `3 failed, 2326 passed, 1 skipped` com exatamente estes
três nomes. Os dois erros de coleta em `tests/unit/export/` também são anteriores —
`caissa.export.docx` não existe (frente F8 em andamento) e o pacote `caissa.export` o
importa no `__init__`. Nenhum dos dois está entre os arquivos que me foram atribuídos e
não toquei em nenhum.

O que posso afirmar sobre o delta é só o que medi diretamente: `tests/unit/typeset` saiu
de **197 passando / 1 pulando** para **238 / 1**, os 41 novos sendo `test_proofsheet.py`.
A contagem total do repositório subiu de 2326 para 2691 entre a primeira e a última
execução; 41 dessa diferença são meus e **não sei explicar o resto** — outras frentes
estão a trabalhar na mesma árvore e não fui verificar o que mudou fora dos meus arquivos.
Registo a discrepância em vez de a apresentar como mérito.

---

## 5. O que continua aberto

Ordenado por quanto incomodaria o crítico.

1. **A reticência do LaTeX** (P5, acima). 1 divergência de texto entre exportadores,
   visualmente nula, medida e não escondida.
2. **A cobertura de hachura abaixo de 35 mm de diagrama** cai a 0,25–0,26 na medida
   raster a 200 DPI (a geometria fica em 0,31). É o regime do piso de impressão. O teste
   não cobre esses dois tamanhos, e disse isso acima.
3. **Peça branca sobre casa clara no tema escuro: 2,18:1.** O crítico listou isto como
   não bloqueante e o par é real, mas a conclusão não segue, e a razão está na mesma
   medida nos outros temas: no tema **book** a mesma razão é **1,00:1**, por desenho, em
   todo livro de xadrez já impresso — a peça branca é um desenho de contorno cujo interior
   é o papel. O que a identifica é o contorno, e é o contorno que a WCAG 1.4.11 mede.
   Contorno sobre casa clara no tema escuro: **7,04:1**; sobre casa escura: **3,09:1**.
   Teste `test_a_piece_is_identified_by_its_outline_in_every_theme` afirma ≥ 3:1 para esse
   par em todos os temas. **Não mudei as cores**, e explico por quê: para levar o corpo
   branco a 3:1 seria preciso escurecer a casa clara até #7E8791, o que derruba o xadrez do
   tabuleiro de 2,28:1 para 1,60:1 — trocaria um par que não carrega informação por um que
   carrega.
4. **A folha de prova tem um vão de 21,5 mm no pé da página 8.** É a fileira de 20/40/60
   mm hachurados, 66 mm de altura, indivisível, que não cabia no que sobrava. A
   justificação vertical absorve o que pode (6 casas por intervalo nessa composição) e o
   resto fica. Numa folha de espécimes prefiro isso a espalhar o vão pelo meio da página.
   As outras onze páginas fecham com 0,4 a 8,4 mm de folga.
5. **Indicador de lance flutuando fora da moldura** (não bloqueante nº 3 da crítica): o
   quadrado e o triângulo continuam com ~0,22 de casa de branco entre eles e o quadro, e
   não têm o mesmo peso óptico (um triângulo de lado *s* tem metade da área de um quadrado
   de lado *s*). Não mexi.
6. **`FrameStyle.shadowed`** continua a desenhar uma sombra deslocada (a 55 % de opacidade,
   não 100 % como a crítica registrou — verifiquei) e continua a deslocar o centro óptico.
   Não é convenção de livro; fica como opção documentada.
7. **Justificação gulosa, não Knuth–Plass.** Sem penalidades globais. O crítico mediu no
   ciclo 1 que a nossa justificação **não é pior** que a da referência (maior vão numa
   linha de prosa: nossa 14 px, referência 17 px), e não é aí que está a diferença.
8. **Sem versaletes em uso** e **sem numeração automática de diagrama no caminho SVG**.
   Ambos existem no código e nenhum é exercido no artefato. Idem ciclo 1.
9. **`⩲ ∓ ⩱` continuam sem sair**, porque Times New Roman não os tem e a substituição é
   fechada por um teste de cobertura de glifo. A solução certa é tirá-los da fonte de
   xadrez, como os livros fazem. Não implementado.
10. **A comparação continua a ser vetor contra digitalização**, e isso nos favorece. O
    ciclo 1 já reconhecia; continua verdade e continua sem PDF nativo de editora para
    corrigir.

---

## 6. Arquivos

**Meus, alterados ou criados neste ciclo:**

```
src/caissa/typeset/board_svg.py   FRAME_RATIO e pesos de moldura; supressao de
                                  coordenadas; hachura reparametrizada; highlight_pair;
                                  knockout das marcas; coordenadas de dentro sobre chapas;
                                  width_for_square; cauda da seta fora da peca de origem
src/caissa/typeset/figurine.py    peso do figurino por contexto (stroke em em do texto)
src/caissa/typeset/latex.py       typeset_moves/moveline/played (casa unica); \cfig,
                                  \caissadots, \gameheading no preambulo; knockout da seta
src/caissa/typeset/fonts.py       handles fechados; ruido do fontTools fora do --verify
tools/typeset_page.py             o compositor: geometria, blocos, fluxo, viuvas e orfas,
                                  grade de linha de base, justificacao vertical;
                                  faces com cmap desambiguado; nao hifenizar nome proprio
tools/typeset_proofsheet.py       reescrita: tudo flui, tudo em portugues acentuado,
                                  uma fonte por pagina de livro, duas fontes distintas
tools/build_latex.py              usa a casa unica; sem \chapter*
tools/build_blind.py              --source e --out; recusa pagina nao cheia; sintaxe
tools/measure_typography.py       NOVO: os criterios de aceite, medidos como o critico
tools/compare_exporters.py        NOVO: SVG contra LaTeX, token a token
tests/unit/typeset/test_proofsheet.py  NOVO: 41 testes, um por criterio
docs/quality/F7_REPORT.md         tres alegacoes falsas corrigidas no lugar
docs/quality/F7_REPORT_C2.md      este arquivo
benchmarks/reports/proofsheet.pdf + proofsheet_png/  regerados (12 paginas)
benchmarks/reports/latex/         regerado
```

**Não toquei** em `docs/quality/F7_CRITIQUE_C1.md`, `benchmarks/reports/critique/`,
`benchmarks/reports/blind/`, `src/caissa/export/`, `core/`, `ocr/`, `notation/`,
`vision/`, `llm/`, `index/`, `ui/`, `pyproject.toml` nem `scripts/`.
