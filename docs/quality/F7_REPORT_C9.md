# F7 — Relatório do construtor, ciclo 9

```
FRENTE: F7 (Tipografia)
CICLO: 9
RESPOSTA A: docs/quality/F7_CRITIQUE_C8.md
BLOQUEANTES DO CICLO 8: 1 (R5 — o fólio não alterna)
```

O ciclo 8 reprovou por **um** item e disse que eram duas linhas. Fiz mais do que duas
linhas, e digo porquê: o defeito não era o `decorate` escrever no sítio errado, era o
compositor não saber o que é um recto. Corrigir só o fólio deixava o mesmo buraco a um
`inner ≠ outer` de distância. Está corrigido na geometria, e o fólio é a primeira coisa
que passa a sair dela.

Todos os números abaixo saem de um comando que corri. Onde o comando é curto está no
texto.

---

## 1. R5 — o fólio alterna. FECHADO.

### O que estava lá

`compose_book_page.decorate` escrevia

```python
canvas.text(geometry.outer, geometry.top - 6, str(page_number + index), size=3.3, fill=ink)
```

`geometry.outer` é `14.0`, uma constante, e `anchor` ficava no `"start"` por omissão. A
`PageGeometry` de `tools/typeset_page.py` tinha `outer` e `inner` e usava `outer` como «a
margem esquerda» em `column_x`, sem paridade nenhuma: **todas as páginas eram compostas
como versos**. A página 45 da folha entregue é um recto e levava o número junto à lombada.

### O que fiz — a geometria, não o `decorate`

`tools/typeset_page.py::PageGeometry` ganhou os dois campos que o modelo do produto já
declarava e que nenhum compositor lia (`src/caissa/core/model/blocks.py`,
`PageGeometry.mirror_margins`), mais o número que falta para saber a paridade:

| campo / método | o que faz |
|---|---|
| `mirror_margins: bool = True` | se `inner` e `outer` trocam de lado entre folhas |
| `first_folio: int = 1` | o número **impresso** da 1ª página da composição |
| `folio(page)` / `is_recto(page)` | paridade pelo número que o leitor vê |
| `left_margin(page)` / `right_margin(page)` | `outer` num verso, `inner` num recto (e vice-versa) |
| `outer_x(page)` / `outer_anchor(page)` | onde vai a mobília de página: `outer` à esquerda num verso, `width − outer` com `anchor="end"` num recto |
| `column_x(index, page=0)` | passou a levar a página; a mancha inteira espelha |

`tp.compose` passou a chamar `geometry.column_x(offset, page)` — antes chamava
`column_x(offset)` sem página nenhuma — e `book_geometry(first_folio, *, mirror_margins)`
passa a paridade adiante. O `decorate` da página de livro ficou:

```python
canvas.text(geometry.outer_x(index), geometry.top - 6, str(geometry.folio(index)),
            size=3.3, fill=ink, anchor=geometry.outer_anchor(index))
```

### A medida, no artefacto entregue

Comando — é o do crítico com uma correção que ele vai querer saber: a `bbox` do PyMuPDF
vem em **pontos**, e o fólio desta folha tem `bbox[1] = 22,85 pt`, de modo que o filtro
`s['bbox'][1] < 14` publicado na crítica não apanha span nenhum. Aqui o limiar está em mm:

```
.venv\Scripts\python.exe -c "import pymupdf; MM=72/25.4; d=pymupdf.open('benchmarks/reports/proofsheet.pdf');
 print([(round(s['bbox'][0]/MM,2), round(s['bbox'][2]/MM,2), s['text']) for i in (10,11,12)
        for b in d[i].get_text('dict')['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans']
        if s['bbox'][1]/MM < 20])"
```

| página | fólio | paridade | ciclo 8 | **ciclo 9** | margem exterior |
|---|---|---|---|---|---|
| `proofsheet.pdf` p11 | 44 | par / verso | 14,00–17,30 mm (esq.) ✔ | **14,00–17,30 mm (esq.)** ✔ | 14,00 mm |
| `proofsheet.pdf` p12 | 45 | **ímpar / recto** | 14,00–17,30 mm (esq.) ✘ | **143,60–146,90 mm (dir.)** ✔ | **14,00 mm** |
| `proofsheet.pdf` p13 | 46 | par / verso | 14,00–17,30 mm (esq.) ✔ | **14,00–17,30 mm (esq.)** ✔ | 14,00 mm |

O span do fólio 45 andou de `x = 14,00–17,30` para `x = 143,60–146,90`: **129,60 mm**. O
crítico estimou 129,9 mm supondo o algarismo com 3,0 mm; o «45» composto mede 3,30 mm, e a
diferença entre as duas contas é a largura do próprio numeral. É o mesmo defeito e a mesma
ordem de grandeza.

### A corrida de quatro páginas que a crítica pediu

As três páginas de livro da folha são três composições de **uma** página cada, portanto só
exercitam `decorate(canvas, 0)`. `benchmarks/reports/proofsheet_run.pdf` é novo neste
ciclo: 4 fólios consecutivos numa **só** composição, emitido pelo mesmo
`tools/typeset_proofsheet.py` (`compose_book_run`), com PNG por página em
`proofsheet_png/run_44..47.png`.

```
44 par/verso   x = 14,00–17,30 mm    -> esquerda   (margem exterior 14,00 mm)
45 ímpar/recto x = 143,60–146,90 mm  -> direita    (margem exterior 14,00 mm)
46 par/verso   x = 14,00–17,30 mm    -> esquerda   (margem exterior 14,00 mm)
47 ímpar/recto x = 143,60–146,90 mm  -> direita    (margem exterior 14,00 mm)
```

Máximo menos mínimo das quatro margens exteriores: **0,00 mm**.

### O portão — um instrumento, duas maneiras de o correr, e a prova de que dispara

O R5 não ficou só num teste. `tools/measure_typography.py` ganhou o subcomando **`folio`**,
irmão do `wordband` que o ciclo 8 elogiou por *reportar a sua própria falha*: mede o
artefacto entregue e **sai com 1** se algum fólio não estiver na margem exterior. Os testes
não reimplementam a regra — importam-na (`mt.folio_spans`, `mt.folio_defects`), porque um
portão cuja linha de comando e cujo teste são dois pedaços de código diferentes só prova
que um dos dois está certo.

```
.venv\Scripts\python.exe tools\measure_typography.py folio
fólio na margem exterior — margem declarada 14.0 mm, tolerância 0.05 mm
  proofsheet.pdf (paginas de livro)
    folio   44  par/verso    x =   14.00–  17.30 mm de 160.9   margem esquerda  14.00 mm   [OK ]
    folio   45  impar/recto  x =  143.60– 146.90 mm de 160.9   margem direita   14.00 mm   [OK ]
    folio   46  par/verso    x =   14.00–  17.30 mm de 160.9   margem esquerda  14.00 mm   [OK ]
  proofsheet_run.pdf
    folio   44  par/verso    x =   14.00–  17.30 mm de 160.9   margem esquerda  14.00 mm   [OK ]
    folio   45  impar/recto  x =  143.60– 146.90 mm de 160.9   margem direita   14.00 mm   [OK ]
    folio   46  par/verso    x =   14.00–  17.30 mm de 160.9   margem esquerda  14.00 mm   [OK ]
    folio   47  impar/recto  x =  143.60– 146.90 mm de 160.9   margem direita   14.00 mm   [OK ]
  7 fólios lidos, 0 defeito(s)
  -> PASSA
folio exit code = 0
```

**A prova de vivacidade.** `--sabotage 1` recompõe a corrida com `mirror_margins=False` —
que **é** o estado que o ciclo 8 entregou por omissão, todas as páginas compostas como
verso — e mede-a com o mesmo instrumento:

```
.venv\Scripts\python.exe tools\measure_typography.py folio --sabotage 1
  proofsheet.pdf (paginas de livro)
    folio   44 ... [OK ]   folio 45 ... [OK ]   folio 46 ... [OK ]      <- não se mexem
  corrida SABOTADA (mirror_margins=False)
    folio   44  par/verso    x =   14.00–  17.30 mm   margem esquerda  14.00 mm   [OK ]
    folio   45  impar/recto  x =   14.00–  17.30 mm   margem direita  143.60 mm   [ERRADO]
    folio   46  par/verso    x =   14.00–  17.30 mm   margem esquerda  14.00 mm   [OK ]
    folio   47  impar/recto  x =   14.00–  17.30 mm   margem direita  143.60 mm   [ERRADO]
  7 fólios lidos, 2 defeito(s)
  -> NAO PASSA
folio --sabotage exit code = 1
```

Dois defeitos, e são os **dois rectos** e mais nada; os três fólios da folha entregue não
se movem um dígito, exatamente como as cinco referências não se movem sob a sabotagem do
`wordband`. E os quatro fólios sabotados caem em `x = 14,00–17,30 mm` — o número que o
crítico mediu na folha do ciclo 8, ao centésimo.

E `passed` exige `len(rows) >= 7` além de zero defeitos: um portão de paridade que não
encontra fólio nenhum não é um portão de paridade que passa. É o modo de falha de todo o
teste do género «não encontrei defeitos».

`tests/unit/typeset/test_proofsheet.py`, **oito testes novos**. Os cinco do R5:

1. **`test_the_folio_sits_on_the_outer_margin_of_every_book_page`** — os spans do PDF
   entregue (p11–13). Também exige que a folha continue a numerar 44/45/46.
2. **`test_the_folio_alternates_over_a_run_of_four_pages`** — o `proofsheet_run.pdf`
   (44–47), e a máxima diferença entre as quatro margens exteriores abaixo de 0,05 mm.
3. **`test_the_folio_parity_check_fails_when_the_folio_is_forced_to_one_side`** — a
   sabotagem acima, dentro da suíte: exatamente dois defeitos, os dois nomeando
   `impar/recto`, os fólios 45 e 47 por essa ordem, e os quatro a 14,0 mm da esquerda.
4. **`test_the_type_area_swaps_sides_with_the_leaf`** e
   **`test_the_drawn_columns_follow_the_mirrored_margins`** — o `mirror_margins` vale para
   a **mancha**, não só para o fólio. Com uma reserva de lombada (`inner=20`, `outer=12`)
   a mancha composta começa a 12,00 mm nos fólios pares e a 20,00 mm nos ímpares, medido
   nos `<text>` filhos diretos do `<svg>` de uma corrida de quatro páginas, e as duas
   colunas mantêm a medida (`column_width` = 61,45 mm em ambas). Com `mirror_margins=False`
   as quatro páginas voltam a 12,00 mm — o comportamento do ciclo 8, ao milímetro.

```
.venv\Scripts\python.exe -m pytest tests/unit/typeset/test_proofsheet.py -q -p no:randomly     -k "folio or mirrored or leaf or recto or blind_harness or half_filled"
-> 8 passed, 103 deselected em 181,87 s
   (o teste mais lento: 66,67 s de setup da folha de 13 páginas + 0,16 s de asserção,
    contra o limite de 120 s por teste do `pytest-timeout` deste projeto)
```

### O que as referências fazem — medido por mim, não citado

O crítico contou 4 referências com fólio lateral e disse que as quatro acertam. Medi eu,
na única referência de que temos o PDF com a página inteira (Quality Chess, *Chess
Structures*, o livro que esta página imita), 12 páginas seguidas, tinta do raster a
200 DPI:

| paridade | tinta da cabeça mais à esquerda | tinta da cabeça mais à direita |
|---|---|---|
| par / verso (6 páginas) | **fólio, 10,9–11,3 mm** | cabeça corrente, acaba a 99,6–100,2 mm |
| ímpar / recto (5 páginas + 1 de abertura) | cabeça corrente, começa a 53,2–58,7 mm | **fólio, 145,8–149,1 mm** |

11 de 11 páginas com fólio lateral acertam a paridade; a décima segunda (idx 51) é uma
abertura de secção com cabeça de largura total e não tem fólio lateral. O fólio salta
**135 mm** entre um verso e um recto. É a convenção, e não é opinião.

### A pergunta que ficou ao lado do R5: as margens são simétricas por decisão

Por **decisão**, e agora declarada em `tools/typeset_proofsheet.py` (`BOOK_INNER_MM`,
`BOOK_OUTER_MM`, com o comentário). A razão é medível e mede-se na mesma referência:

```
trim 160,87 mm  (pixel = 0,127 mm a 200 DPI)
par/verso    n=6  margem esq 11,03 mm  margem dir 10,99 mm
ímpar/recto  n=6  margem esq 11,09 mm  margem dir 11,07 mm
assimetria média |esq−dir| = 0,032 mm ; diferença par × ímpar na esquerda = 0,063 mm
```

**A Quality Chess compõe este livro com margens simétricas.** As duas diferenças, 0,032 e
0,063 mm, são um quarto e metade de um pixel a 200 DPI: não são medíveis, quanto mais
intencionais. A editora que estamos a imitar não dá reserva de lombada nesta obra, e a
folha faz o mesmo. O que **não** é opcional é o fólio, e esse alterna mesmo com
`inner == outer` — que é precisamente por que o R5 era um defeito e a simetria das margens
não é.

E digo o que a mesma medida diz contra nós: **a margem da referência é 11,0 mm e a nossa é
14,0**. Somos 3 mm mais largos de margem. Isso é uma decisão de medida anterior a este
ciclo (a coluna sai a 63,45 mm contra os «cerca de 63 mm» que o `BODY_PT` documenta na
referência, com a diferença a ir para o gutter em vez da margem), não é a simetria, e não
lhe toquei: mudar a medida re-quebra todas as linhas. Fica nomeado.

O caminho para o contrário está aberto e testado: `PageGeometry(inner=20, outer=12)` e a
mancha espelha sozinha, com o teste a prová-lo. Não o liguei na folha porque mudar a
medida da coluna re-quebra todas as linhas e invalidaria as medidas de espaço entre palavras
que o ciclo 8 acabou de adjudicar — e ninguém pediu.

### `different_odd_even`, o segundo campo do modelo

`SectionBreak.different_odd_even` também não era lido por compositor nenhum.
`compose_book_page` passou a aceitar `different_odd_even` e `recto_running_head`, e
`test_the_running_head_can_differ_on_recto_and_verso` prova que o recto troca de cabeça e
o verso não. **Fica desligado na folha entregue, por decisão**: as três páginas de livro
partilham a mesma cabeça corrente (`Family One – d4 and …d5`), inventar uma segunda cabeça
seria autoria, e o ciclo 8 já registou uma contradição de autoria nesta fonte. O mecanismo
está ligado ao modelo e medido; o conteúdo não mudou.

---

## 2. `render_ours` volta a emitir — e a contagem de colunas curtas

**Reprodução do estado do ciclo 8** (é o número do crítico, ao dígito):

```
mareco  pages=1  ['52/53', '52/53']  feet [207.892, 207.892]  spread 0.0000  residual [0, 0]
rios    pages=1  ['52/53', '52/53']  feet [207.892, 207.892]  spread 0.0000  residual [0, 0]
-> render_ours RECUSAVA as duas fontes: 2 de 2 colunas «curtas» em cada uma, 4 no total.
```

**A causa.** O portão dizia `c.used < c.capacity`. Mas `tp.compose(balance_last=True)`
não compõe até à capacidade da grade: compõe o último espalhamento até à altura natural da
coluna mais alta (`feather(tail, target=max(used))`). Numa composição de uma página,
**todas** as páginas são o último espalhamento. Logo o máximo que uma página cheia pode
atingir é a altura da sua própria matéria — 52 — e o portão pedia 53. Era impossível de
satisfazer, e o ciclo 7 entregou o arnês partido sem o dizer.

**A correção.** O portão fica — existe porque a amostra A do ciclo 1 «parou a y=1479 com
conteúdo por compor» e foi um dos sinais que a denunciaram — mas passa a medir as duas
coisas que denunciam mesmo uma página meia-cheia, ambas declaradas em
`tools/build_blind.py`:

* `FULL_PAGE_SLACK = 1` slot — nenhuma coluna pode ficar mais de um slot abaixo da
  capacidade. A amostra do ciclo 1 estava ~11 slots curta; a entregue está a 1.
* `FULL_PAGE_FOOT_MM = 0.01` — os dois pés têm de fechar.

**Depois:**

```
mareco {"columns_used_capacity": ["52/53","52/53"], "short_column_slack_slots": [1,1],
        "foot_spread_mm": 0.0, "column_feet_mm": [207.892,207.892]}   PNG 560 830 B, PDF 2 461 498 B
rios   {"columns_used_capacity": ["52/53","52/53"], "short_column_slack_slots": [1,1],
        "foot_spread_mm": 0.0, "column_feet_mm": [207.892,207.892]}   PNG 586 823 B, PDF 2 410 979 B
```

**Contagem de colunas curtas pedida: 0 de 4** (era 4 de 4). As duas fontes emitem. Os dois
números novos (`columns_used_capacity`, `short_column_slack_slots`) vão para o
`answers/*.json` do conjunto cego, para que o próximo crítico veja a folga sem ter de a
reproduzir.

**A prova de vivacidade deste portão também:**
`test_the_full_page_gate_still_refuses_a_half_filled_page` dá a `render_ours` metade da
fonte inglesa e exige `SystemExit` com «nao enche a pagina». Relaxar um portão sem provar
que ele ainda dispara é cegá-lo.

---

## 3. `move → body` — melhorado e medido, não fechado. Sem mudança neste ciclo.

Medido no compositor, que é o único sítio onde as classes de vão são conhecidas (o
`gapaudit.py` do ciclo 5 está morto e o ciclo 8 confirmou-o apagando a leitura do PDF do
ficheiro):

```
.venv\Scripts\python.exe -c "...compose_book_page(...).unequal_gaps()"
mareco  {'move->body': [0, 1, 1, 1, 1]}   pés [207.892, 207.892]  desnível 0.0000 mm
rios    {}                                 pés [207.892, 207.892]  desnível 0.0000 mm
```

Idêntico ao ciclo 8. Uma classe desigual na página inglesa, nenhuma na portuguesa, um slot
de diferença — **3,671 mm** de grade, uma entrelinha. Não mexi, e digo porquê, com a conta
à vista: são **quatro** vãos `move->body` a 1 slot na coluna esquerda contra **um** a 0 na
direita. Mantê-los iguais significa pô-los todos a 0, e a coluna esquerda encurta 4 slots
= 4 × 3,6713 = **14,685 mm** — que é, ao milésimo, o `desnivel 14.684 mm` que o `feather`
já documenta como o preço medido da alternativa. Duas colunas a acabar a 14,7 mm uma da
outra é pior do que um par de blocos a duas alturas numa coluna; foi o que o ciclo 6
decidiu e o ciclo 8 não contestou. Fica em aberto e fica contado.

---

## 4. O que não mudou, e está verificado por mim neste ciclo

* **O artefacto é o que o código produz.** Rasterizei o entregue e uma recomposição feita
  agora, a 300 DPI:

  ```
  proofsheet_rios.pdf p1  : raster diff mean = 0.0000, max = 0
  proofsheet.pdf p11      : raster diff mean = 0.0000, max = 0
  proofsheet.pdf p12      : raster diff mean = 0.0000, max = 0   (a página do fólio novo)
  proofsheet.pdf p13      : raster diff mean = 0.0000, max = 0
  ```

* **A vantagem do espaço entre palavras não se moveu um dígito.**
  `.venv\Scripts\python.exe tools\measure_typography.py wordband`:

  ```
  F nossa, pt (amostra_F)   just 22/45  banda 0.71–1.33 = 1.89x  desvio 0.160  fora 2/22 (9.1 %)
  A Quality Chess p149      3.57x / 0.327 / 47.4 %      B Nunn p50      2.55x / 0.258 / 31.4 %
  C Gambit p116             3.00x / 0.263 / 34.6 %      D Everyman p215 3.50x / 0.394 / 51.1 %
  E Dvoretsky p215 (bandeira, 7/42)  1.21x / 0.073 / 0.0 %
  contra as quatro que justificam -> PASSA (3 de 3);  contra as cinco -> NAO PASSA (0 de 3)
  wordband exit code = 1
  ```

  O instrumento continua a **reportar a sua própria falha**. É o que o ciclo 8 elogiou e
  não é para se perder.

* **A galeria não se mexeu.** As 10 páginas de espécime começam a mancha a **14,00 mm**,
  as dez. Com `inner == outer` o espelhamento é a identidade, e isso é medido, não assumido.

* **O exportador LaTeX já acertava a paridade e continua a acertar.** `livro.pdf`,
  fólio 1 (ímpar/recto), span `'1'` a x = 145,16–146,91 mm de 160,9 — acaba a **13,99 mm**
  da margem direita. `\documentclass[10pt,twoside]{book}` faz isto sozinho. Vale
  a pena dizer o que isso significa: **o defeito do R5 era só do compositor nativo**, e os
  dois exportadores agora concordam também na mobília da página, não só no texto.
  `livro.tex` regenerado é **byte a byte igual** ao que o ciclo 8 entregou (8 154 B,
  `diff` vazio contra `benchmarks/reports/critique/c8/tex/base.tex`).

* **Olhei as 18 páginas com os olhos**, a 200 DPI: as 13 de `proofsheet.pdf`, a `rios`, e
  as 4 da corrida nova. Nada fora da mancha, nada cortado, os fólios onde a aritmética diz.

---

## 5. O que continua em aberto, declarado

1. **`move → body` a duas alturas na página inglesa** — §3 acima. 1 classe, 1 slot.
2. **Figurinos em linha os mais leves do conjunto cego** (134,2 de cinza médio contra
   122,2 da segunda). O crítico retirou a acusação no ciclo 8; o número fica.
3. **Dois pés abertos de espécime**, p3 e p8 — preço declarado de não partir uma grelha de
   seis espécimes ao meio. Confirmado a olho neste ciclo: a p3 tem `2. Molduras` e as suas
   seis molduras; a p8 tem as dez últimas famílias da secção 7.
4. **`book_source_mareco` contradiz-se** (`Final remarks` culpa `17…♘d7`, lance que não
   aparece na página). **Não mexi.** É autoria, o ciclo 5 arrumou a categoria e o ciclo 8
   confirmou-a, e reescrever a cópia re-quebra todas as linhas da página que acabou de ser
   medida. Fica nomeado, não fica corrigido.
5. **`inner == outer`** — decisão declarada em §1, com a medida da referência que a
   justifica. O mecanismo para o contrário está ligado e testado.

---

## 6. Ficheiros

**Alterados**

* `tools/typeset_page.py` — `PageGeometry` sabe o que é um recto (`mirror_margins`,
  `first_folio`, `folio`, `is_recto`, `left_margin`, `right_margin`, `outer_x`,
  `outer_anchor`, `column_x(index, page)`); `compose` passa a página ao `column_x`.
* `tools/typeset_proofsheet.py` — `book_geometry(first_folio, *, mirror_margins)`;
  `BOOK_INNER_MM`/`BOOK_OUTER_MM` declarados; `compose_book_page` escreve o fólio na
  margem exterior e aceita `different_odd_even` / `recto_running_head` / `mirror_margins`
  / `repeat`; `compose_book_run` novo; `main` emite `proofsheet_run.pdf` e os PNG da corrida.
* `tools/build_blind.py` — o portão de página cheia mede folga e desnível
  (`FULL_PAGE_SLACK`, `FULL_PAGE_FOOT_MM`) em vez de exigir a capacidade da grade; o
  `answers/*.json` leva os dois números novos.
* `tools/measure_typography.py` — subcomando **`folio`** novo, com `--sabotage 1`, que sai
  com 1 quando um fólio não está na margem exterior (`folio_spans`, `folio_defects`,
  `measure_folio`, `FOLIO_TOL_MM`, `FOLIOS_EXPECTED`); e `column_x` passou a receber a
  página (identidade hoje, correto amanhã).
* `tests/unit/typeset/test_proofsheet.py` — 8 testes novos, que **importam** o instrumento
  do `measure_typography` em vez de o reimplementar (310 recolhidos, eram 302).

**Novos artefactos**

* `benchmarks/reports/proofsheet_run.pdf` — a corrida 44–47 numa só composição.
* `benchmarks/reports/proofsheet_png/run_44..47.png`.

**Regenerados**

* `benchmarks/reports/proofsheet.pdf`, `proofsheet_rios.pdf`, `proofsheet_png/*`,
  `benchmarks/reports/latex/livro.{tex,pdf,log}`, `latex/page_01.png`.

---

## 7. Suíte

```
.venv\Scripts\python.exe -m pytest -q -p no:randomly
-> 2997 passed, 1 skipped em 665,90 s (0:11:05), exit 0
   2998 recolhidos; o único skip é o do Brotli (`test_fonts.py:253`, WOFF2 sem compressor)

.venv\Scripts\python.exe -m pytest tests/unit/typeset -q -p no:randomly
-> 309 passed, 1 skipped em 333,17 s (0:05:33), exit 0   (eram 301 + 1 no ciclo 8)
```

**Sobre o número.** A linha de base do enunciado é **2987 passed, 1 skipped**. 2987 + os
meus 8 testes = 2995, e a suíte mede **2997**: apareceram **2 testes fora de
`tests/unit/typeset`** enquanto eu trabalhava. Não são meus — a frente F7 é
`tests/unit/typeset`, que passou de **302** para **310** recolhidos (+8), e os outros
2 688 são de outra frente a mexer em `src/caissa/ui/` e no `qt/` do tronco ao mesmo tempo.
**0 falhas em toda a suíte**, que é a parte que me diz respeito.
