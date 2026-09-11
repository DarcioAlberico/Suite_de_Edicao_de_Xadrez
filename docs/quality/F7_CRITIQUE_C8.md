# F7 — Crítica adversarial, ciclo 8

```
VEREDITO: REPROVADO
CICLO: 8
FRENTE: F7 (Tipografia)
```

> **Nota de procedimento.** A Fase 1 inteira — ordenação, defeitos por amostra e o palpite
> real×gerado — foi medida, escrita e gravada em `benchmarks/reports/critique/c8/phase1.md`
> **antes** de eu abrir `GABARITO.json` e **antes** de abrir qualquer documento de histórico.
> O único documento lido antes da Fase 1 foi `docs/quality/CRITIC_CHARTER.md`. A tabela
> abaixo é cópia literal desse ficheiro. Não usei tamanho de ficheiro, data nem metadados
> PNG. Todos os números são meus, por scripts em `benchmarks/reports/critique/c8/`.
>
> Encontrei nesse diretório cinco ficheiros de 8 de setembro (`phase1_measure.py`,
> `phase1_boxes.py`, `phase1_boards.py`, `phase1_*.json`) de uma tentativa anterior deste
> ciclo apontada ao conjunto **blind4**. Não os li antes da Fase 1 e o meu `phase1.md`
> substituiu o que lá estivesse. Registo-o para quem contar artefactos.

---

## Comparação às cegas

*(preenchido ANTES de saber qual é a nossa — cópia literal de `critique/c8/phase1.md` §1)*

| Amostra | Posição | Justificativa |
|---|---|---|
| **E** | **1º** | Tabuleiros quadrados, figurinos cheios e com o peso do texto, ligaduras reais, os espaços entre palavras mais apertados de qualquer amostra justificada (6–13 px numa medida de 65,8 mm), colunas fecham a 1,9 mm. |
| **F** | **2º** | Mesma qualidade de tipo que E, mas os seus três tabuleiros são **1,0–1,4 % mais largos que altos**, o espaço entre palavras salta de 10 para 25 px dentro do mesmo parágrafo, e dois diagramas lado a lado estão 4,1 mm fora de registo vertical. |
| **B** | **3º** | A melhor geometria de diagrama e o melhor equilíbrio de colunas das seis (tabuleiros quadrados a 0,01 %, pés a 0 px, hifenização a funcionar) — mas o fólio está na margem errada, os figurinos em linha são o desenho do diagrama (contorno com bandas cinzentas, oticamente leves na linha) e um diagrama traz um retângulo de casa selecionada. |
| **A** | **4º** | Nunca justifica, por isso não tem uma única linha má — mas não é tipografia de livro: ~15 pt numa página de 216 × 279 mm, painéis cinzentos de arestas duras por trás de parágrafos, uma caixa arredondada com biselado 3-D, coordenadas sem serifa contra um texto com serifa. |
| **C** | **5º** | A aresta direita mais disciplinada das seis (12,1 % de dispersão, 74 linhas justificadas) e hifenização correta, mas os espaços entre palavras vão de 6 a 21 px na mesma página e palavras vizinhas colidem; as colunas acabam a 8,3 mm uma da outra — o pior desnível do conjunto. |
| **D** | **6º** | Letras partidas e borratadas; vãos de 5 a 21 px (4,2:1) com palavras visivelmente coladas; hachura degradada nas filas de cima do diagrama. |

**Identidade revelada: a nossa era a amostra B, classificada em 3º de 6.**

| Amostra | Origem (GABARITO) | Minha posição | Meu palpite real × gerado |
|---|---|---|---|
| A | referência — Dvoretsky 2025 p147 | 4º | real ✔ |
| **B** | **nossa — folha regenerada p45, ajuste total (ciclo 7)** | **3º de 6** | **gerada ✔** |
| C | referência — Gambit p147 | 5º | real ✔ |
| D | referência — Nunn p181 | 6º | real, digitalizada ✔ |
| E | referência — Everyman/Aagaard p215 | 1º | real ✔ |
| F | referência — Quality Chess p181 | 2º | real ✔ (com a ressalva registada) |

Acertei as seis origens. **A ordenação cumpre a §2.1 na primeira metade** — 3º de 6, e as
duas referências que ficaram atrás de nós ficaram por defeitos que também nomeei nelas.

**O que a denunciou** (`phase1.md` §3, escrito antes da revelação, por ordem de peso):

1. **O fólio na margem interior de uma página ímpar.** É o primeiro item da minha lista e é
   o único dos quatro que é um defeito tipográfico. Ver bloqueante nº 1.
2. Os figurinos em linha desenhados com o contorno do diagrama.
3. O retângulo de casa selecionada em h7.
4. O texto contradizer-se (`Final remarks` culpa `17…♘d7`, lance que não aparece na página).

Dos quatro, **retiro dois** depois de medir as referências com o mesmo instrumento — ver
"Duas acusações que retiro". O nº 4 é autoria, não composição, categoria que o ciclo 5 já
tinha arrumado como não bloqueante. **Fica o nº 1**, e a §2.1 é explícita: *«você não pode
ter apontado nela nenhum defeito que não tenha apontado também nas outras»*.

### A assimetria vetorial × digitalização, medida em vez de suposta

O enunciado pediu para eu verificar. Fiz três testes (`glyphvar.py`, `tmpl2.py`, `scan.py`,
`hatch2.py`, `frame.py`).

| | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| repetições de glifo **idênticas ao pixel** (NCC ≥ 0,975) | 94,1 % | *nenhum molde chega a 10 casos* | 94,7 % | 43,6 % | 92,5 % | *nenhum molde chega a 10 casos* |
| MAD mediano das repetições | 0,00 | — | 0,00 | **8,01** | 0,00 | — |
| ruído de papel (desvio na banda de margem) | 0,00 | 0,00 | 0,00 | 0,00 | 21,2 (é o fólio) | 0,00 |
| inclinação de linha de base | 0,00° | −0,10° | 0,00° | 0,00° | −0,05° | +0,10° |

**Só a D é uma digitalização** — é a única com rasters de glifo genuinamente diferentes entre
instâncias, e tem tinta borratada e caracteres partidos a confirmá-lo. A, C e E colocam os
glifos em posições inteiras (94 % de repetições idênticas), o que é ou um render vetorial com
*grid-fitting* ou um dicionário de símbolos JBIG2; B e F posicionam a sub-pixel.

**Quanto isso moveu a ordenação: quase nada.** Só desceu a D, e disse explicitamente no
`phase1.md` que não conto as formas degradadas da C contra a **composição** dela, só o
espacejamento. Nada nisto ajudou ou prejudicou a nossa.

O teste dos tabuleiros que o enunciado pediu (diferença de pixels entre casas escuras na
mesma página) não separa nada porque a hachura de E e F é tracejada e o estimador fica
ruidoso; o que separa é a **moldura medida a sub-pixel**, e é a medida que dá o defeito de F:

| | A | B (nossa) | D | E | F |
|---|---|---|---|---|---|
| moldura L/A por tabuleiro | 0,9991 | **1,0000 · 0,9999 · 1,0000** | 0,9995 | 1,0018 · 1,0033 | **1,0138 · 1,0102 · 1,0122** |
| variação de tamanho entre tabuleiros da mesma página | — | **0,03 px** | — | 1,0 px | 1,6 px |

Os nossos três tabuleiros são quadrados a 0,01 % e iguais entre si a **0,03 px**. Os da
Quality Chess são 1,0–1,4 % mais largos que altos. É a melhor geometria de diagrama do
conjunto e é nossa.

---

## A vantagem do ciclo 7, adjudicada

Esta era a única condição em aberto. **A vantagem é real.** E é maior e melhor fundada do
que o construtor a vendeu — ele liderou com a estatística mais fraca das três.

### 1. Reproduzi o número, três vezes

```
.venv\Scripts\python.exe tools\measure_typography.py wordband     (3 execuções)
```

As três execuções saem **idênticas ao dígito**, e a tabela do relatório do ciclo 7 reproduz
carácter a carácter. Mediana = qualquer uma delas.

E o artefacto não está podre: rasterizei `proofsheet_rios.pdf` p1 a 300 DPI e comparei-o com
uma página **recomposta do código atual** (`critique/c8/reband.py`) — `raster diff mean =
0,0000, max = 0`. Bit a bit. A medida não é de um PDF antigo que ninguém consegue refazer.

### 2. A prova de vivacidade dispara, e só na nossa página

```
.venv\Scripts\python.exe tools\measure_typography.py wordband --sabotage 4
```

| | banda | desvio | fora da banda | veredicto |
|---|---|---|---|---|
| entregue | 1,889 | 0,160 | 9,1 % | PASSA (3 de 3) contra as quatro |
| sabotado | **3,667** | **0,502** | **40,9 %** | **NÃO PASSA (0 de 3)**, também contra as quatro |

As cinco referências saem **idênticas ao dígito** nas duas execuções (A 3,57/0,327/47,4 %;
B 2,55/0,258/31,4 %; C 3,00/0,263/34,6 %; D 3,50/0,394/51,1 %; E 1,21/0,073/0,0 %). Os três
números que o construtor alegou são exatamente os que eu obtive. **Portão vivo.**

E — isto conta — `main()` devolve `0 if report["passed"]`, onde `passed` é o veredicto
**contra as cinco**. Confirmei: `wordband exit code = 1`. O instrumento do construtor
**reporta falha**. Ele não se auto-certifica.

### 3. Medi eu a dispersão da aresta direita de E. O construtor tem razão.

Código meu, sem importar nada dele (`critique/c8/ragged.py`). Dispersão = (p90 − mediana)
das arestas direitas, em % da medida:

| | A QC | B Nunn | C Gambit | D Everyman | **E Dvoretsky** |
|---|---|---|---|---|---|
| dispersão col. esq. / dir. | 0,57 % / 0,57 % | 0,24 % | 0,18 % / 0,26 % | 0,19 % / 0,19 % | **9,50 % / 7,98 %** |
| linhas de corpo que chegam à margem | 66,7 % / 62,1 % | 94,6 % | 93,2 % / 93,2 % | 56,2 % / 88,2 % | **17,4 % / 17,4 %** |

Uma ordem de grandeza. O construtor reportou 8,8 %/6,0 %; eu meço 9,50 %/7,98 %, na mesma
escala e com a mesma conclusão. **A E não justifica**, e isso não é leitura, é contagem.

**Adjudicação da categoria.** «Banda mais apertada que todas as referências que justificam»
não é uma categoria escolhida para ganhar. É a única categoria em que a medida significa
alguma coisa. A banda de espaço entre palavras mede a **variância que a justificação
introduz**; uma página em bandeira não estica nada e por construção tem variância zero.
Medir a banda da E é medir a ausência da operação, e nenhuma página justificada, de nenhuma
editora, pode ganhar essa conta a uma página em bandeira. A exclusão é de princípio e é
simétrica — não exclui «páginas que nos ganham», exclui páginas que não executam a operação
medida — e a regra reaplicada a um conjunto novo voltou a apanhar a Dvoretsky sozinha.

**Mas digo também o que isso custa à alegação:** compor em bandeira é uma resposta
legítima ao mesmo problema, e a página da Dvoretsky não tem uma linha frouxa nem uma
apertada. A formulação honesta da vantagem é *«a melhor composição justificada do
conjunto»*, não *«a melhor tipografia»*. O construtor escreve-a assim. Aceito-a assim.

### 4. Replicação num conjunto que ninguém mediu — e é aqui que a vantagem fica de pé

O teste do ciclo 7 corre sobre `blind3`, o conjunto do ciclo 5. Corri a **mesma regra do
construtor** sobre o **blind5**, com as caixas de coluna que eu próprio desenhei na Fase 1,
antes de saber qual amostra era a nossa (`critique/c8/blind5band.py`). Cinco livros
diferentes, páginas inéditas, e **a nossa página é outra** (p45 em inglês, não a `rios` em
português):

| página blind5 | justificadas | banda | desvio | fora de 0,85–1,50 |
|---|---|---|---|---|
| A Dvoretsky 2025 p147 | **9/53** (bandeira) | 1,36× | 0,088 | 0,0 % |
| **B — NOSSA p45** | 15/41 | **2,14×** | **0,297** | **6,7 %** |
| C Gambit p147 | 85/90 | 3,17× | 0,324 | 44,6 % |
| D Nunn p181 | 59/70 | 3,33× | 0,335 | 50,8 % |
| E Everyman/Aagaard p215 | 48/65 | 3,50× | 0,394 | 51,1 % |
| F Quality Chess p181 | 19/40 | 3,50× | 0,405 | 52,6 % |

Ganha as três contra as quatro que justificam; perde as três à mesma página em bandeira, e
à mesma editora que no ciclo 7. **A alegação replica em material fresco, com outra página
nossa, com caixas minhas.** É o teste que faltava ao ciclo 7 e passa.

Como subproduto: a Quality Chess p181 mede 3,50× / 0,405 / 52,6 % — o que confirma por um
segundo instrumento o que eu tinha visto a olho na Fase 1, o salto de 10 px para 25 px de
espaço entre palavras dentro de um parágrafo dela.

### 5. A objeção que nenhum ciclo testou: a banda é um artefacto do tamanho da amostra?

`max/min` cresce com *n* por construção. Nós justificamos 15–22 linhas por página; as
referências justificam 35–85. Se a vantagem for isso, não é vantagem.

Testei (`critique/c8/subsample.py`): 20 000 sorteios de *n* = o nosso *n* das razões de cada
referência, e a distribuição da banda que ela mostraria ao nosso *n*.

**blind3 (conjunto do ciclo 7), o nosso *n* = 22, a nossa banda = 1,889:**

| referência | banda a *n* cheio | mediana a *n*=22 | p05 | **P(referência < a nossa)** |
|---|---|---|---|---|
| A Quality Chess | 3,57 | 2,86 | 2,43 | **0,0 %** |
| B Nunn | 2,55 | 2,27 | 1,82 | **10,2 %** |
| C Gambit | 3,00 | 2,50 | 2,00 | **1,7 %** |
| D Everyman | 3,50 | 3,33 | 2,62 | **0,0 %** |

**blind5 (fresco), o nosso *n* = 15, a nossa banda = 2,143:** C 8,6 % · D 4,2 % ·
E 1,4 % · F 2,7 %.

A banda sobrevive à correção contra 7 das 8 colunas de referência a p < 0,05; contra a Nunn
fica a p ≈ 0,10, que é uma vantagem fraca e digo-o.

**E é por isso que a estatística que decide não é a banda.** O **desvio** e a **fração fora
de 0,85–1,50×** são estimadores por linha, **independentes de *n***, e não sofrem nada desta
correção:

| | nossa | pior referência que justifica | melhor referência que justifica | fator |
|---|---|---|---|---|
| fora da banda, blind3 | **9,1 %** | D 51,1 % | B 31,4 % | **3,5× a 5,6×** |
| fora da banda, blind5 | **6,7 %** | F 52,6 % | C 44,6 % | **6,7× a 7,9×** |

**Uma linha em 11 a 15 fora da banda aceitável, contra uma em 2 a 3 em todas as cinco
páginas justificadas de dois conjuntos independentes.** Isso é a vantagem, é robusta,
é n-independente, é o que um leitor vê, e o construtor listou-a em terceiro lugar.

**Conclusão da §5.1: a condição de aprovação que restava está CUMPRIDA.** Não é empate.

---

## Os dois instrumentos que o construtor contestou

Tem razão nos dois. Verifiquei os dois eu, e não pela leitura do argumento dele.

### `critique/c5/gapaudit.py` — **QUEBRADO. Confirmado da maneira mais dura possível.**

O script abre `proofsheet.pdf`, carrega os spans da p10 para `rows`… e nunca mais usa `rows`.
Tudo o que imprime sai de `SEQ`/`SEQR`, duas tabelas de linhas de base **escritas à mão** no
ciclo 5, e de `LEAD=10.406`.

Copiei-o para `critique/c8/` e corri três versões:

```
gapaudit.py            (original, p10)  ─┐
gapaudit_page1.py      (apontado à p1)   ├─ saída BYTE A BYTE IDÊNTICA
gapaudit_nopdf.py      (leitura do PDF APAGADA) ─┘
```

Com a leitura do PDF **removida do ficheiro**, imprime exatamente o mesmo. Não é um
instrumento com um viés; é um `print` de uma tabela. **O não bloqueante nº 1 do ciclo 5 fica
sem prova instrumental**, e qualquer afirmação de que foi «melhorado e medido» com ele é
nula. Medi-o de novo por dois caminhos independentes — ver não bloqueante nº 1.

### «0 over/underfull boxes» — **é uma afirmação sobre a tolerância. Reproduzi ao dígito.**

Copiei `benchmarks/reports/latex/livro.tex` para `critique/c8/tex/` (não toquei no
entregue) e compilei três vezes:

```
default                                  0 mensagens
\multicoltolerance=200 \tolerance=200     Overfull \hbox (1.90569pt too wide) at lines 102--102
\hbadness=99 \hfuzz=0pt                  0 mensagens
```

O `1.90569pt` do construtor é exatamente o meu. **Quanto vale aquele zero:** vale *uma* coisa
concreta — com `\hbadness=99` na tolerância por omissão o log não acusa nada, o que quer dizer
que **nenhuma linha do documento passa de badness 99**, isto é, nenhuma é *very loose* na
contabilidade do próprio TeX. Isso não é nada. Como prova de que a composição está apertada,
vale **zero**: `multicol` põe `\multicoltolerance=9999`, com 9999 o TeX aceita quase qualquer
badness antes de admitir um overfull, e há de facto um overfull de 1,9 pt escondido. Dois
críticos citaram-no como evidência de qualidade e citaram uma tautologia.

Que o construtor tenha ido verificar e **retirado uma afirmação que este projeto repetia** —
sem lhe ser pedido, e contra si — é a coisa certa e conta.

---

## A regressão das colunas curtas — e ela é maior do que o enunciado diz

Reproduzi (`critique/c8/repro_rios.py`, a escrever só em `critique/c8/answers/`):

```
source=mareco: col0 52/53 SHORT, col1 52/53 SHORT   -> render_ours RECUSA
source=rios  : col0 52/53 SHORT, col1 52/53 SHORT   -> render_ours RECUSA
```

**A regressão não é só na `rios`. É nas duas fontes.** `build_blind.render_ours` não consegue
emitir amostra cega nenhuma. O ciclo 7 entregou um estado em que o arnês cego não corre e não
o disse.

**Vale a pena bloquear pelas colunas curtas? Não, e digo porquê com números.**
Os dois pés fecham em 207,892 mm, `foot_spread = 0,0000 mm`, e o bloco de texto acaba
**4,7 mm — 1,2 entrelinhas — acima** do pé de desenho (`bottom=16,0 mm`). Uma linha de branco
a mais, igual nas duas colunas. No conjunto fresco, **duas referências fazem pior no mesmo
eixo**: a Gambit fecha as colunas a 8,3 mm uma da outra e a Dvoretsky a 4,6 mm; a nossa fecha
a 0,0. Uma página cujo texto acaba uma linha acima do pé, com as duas colunas ao mesmo nível,
é o que um livro faz quando a matéria não dá para mais — não é um defeito tipográfico.

O que **é** um problema é de processo, não de página: o portão existe porque no ciclo 1 a
nossa amostra se denunciou por não encher, ele está a disparar nas duas fontes, e o relatório
do ciclo 7 não o menciona. Fica como não bloqueante nº 3.

---

## Fase 3 — a folha de 13 páginas, olhada a 400 e 600 DPI

Medi os pés das 13 páginas do PDF a 600 DPI (`critique/c8/feet.py`) e re-renderizei a p3, a
p8 e a p11 a 400 DPI para `critique/c8/`.

| página | pé aberto abaixo do bloco de texto |
|---|---|
| p1 4,7 mm · p7 6,0 mm · p5 17,1 mm · p6 20,2 mm · p2 24,4 mm · p4 32,3 mm | — |
| **p3** | **76,4 mm** |
| **p8** | **116,0 mm** |
| p11 · p12 · p13 · `rios` | **0,0 mm — pé cheio, 20,0 mm de margem, os quatro iguais** |

Os dois pés grandes são os que o ciclo 7 declarou (79,9 e 119,7 mm medidos da caixa de bloco;
eu meço da tinta, daí os ~3,5 mm de diferença). **Olhei a p3 a 400 DPI:** `2. Molduras` no
topo, o parágrafo de abertura, as seis molduras em grelha 3×2, e depois 42 % da página em
branco. A secção está inteira e legível; o branco é o preço de não partir uma grelha de seis
espécimes. **O órfão do ciclo 5 está fechado** — o título e os seus seis espécimes estão na
mesma página, e vi-o, não o li.

**Isto não bloqueia**, por uma razão simples: são páginas de **espécime**, não de livro. As
quatro páginas de livro — as que a frente F7 é julgada a compor — fecham o pé exatamente,
nas duas colunas, nas quatro. É o inverso do caso mau.

---

## Duas acusações que retiro

Por dever da §2.1, porque as escrevi contra a nossa amostra na Fase 1 e depois medi as
referências com o mesmo instrumento.

**Os figurinos em linha «leves demais».** Medi o corpo de cada figurino em linha das seis
páginas (`critique/c8/weight2.py`, fechamento morfológico e erosão, depois a média do cinza
do interior): nossa **134,2** · Quality Chess 122,2 · Gambit 121,6 · Everyman 101,3 ·
Nunn 86,5 · Dvoretsky 71,6. Somos os mais leves, mas por **10 %** sobre a Quality Chess, que
tem 19,6 % do corpo do glifo em cinza médio contra os nossos 19,1 %; e a Dvoretsky usa
figurinos em **contorno** para as peças brancas. Contorno com detalhe interior não é
impossível num livro publicado — duas referências fazem-no. **Retiro a acusação**; fica como
observação não bloqueante.

**O retângulo de casa selecionada em h7.** Fui ver o que ele marca: o diagrama é
`After 21.♗xh7†` e h7 é a casa de captura; a seta g3→g7 é a subida da torre. A marcação está
**editorialmente correta**, é legível a 200 DPI, e está desenhada **por baixo** das peças, de
modo que nenhuma peça é ocultada. Nenhuma referência desta folha mostra a capacidade.
**Retiro a acusação, e conta a favor.**

---

## Defeitos bloqueantes

### 1. O fólio não alterna. Na folha entregue, a página 45 leva o número junto à lombada.

**Onde:** `tools/typeset_proofsheet.py::compose_book_page`, a função `decorate`, que escreve
`canvas.text(geometry.outer, geometry.top - 6, str(page_number + index), …)` — e
`book_geometry()` devolve `outer = 14.0`, uma constante. `tools/typeset_page.py::PageGeometry`
tem campos `outer` e `inner` mas usa `outer` como «margem esquerda» (`column_x` linha 1167);
não há em toda a `typeset_page.py` uma única ocorrência de `recto`, `verso`, `odd`, `even` ou
paridade de página.

**O que:** o entregável tem uma corrida real de três páginas numeradas. Extraídas do PDF:

```
proofsheet.pdf p11:  span '44'  em x = 39,7–49,0 pt = 14,0–17,3 mm   (par  -> esquerda ✔)
proofsheet.pdf p12:  span '45'  em x = 39,7–49,0 pt = 14,0–17,3 mm   (ÍMPAR -> devia ser direita ✘)
proofsheet.pdf p13:  span '46'  em x = 39,7–49,0 pt = 14,0–17,3 mm   (par  -> esquerda ✔)
```

Numa página de 160,9 mm de largura, o fólio de uma recto pertence a x = 143,9–146,9 mm. Está
a **129,9 mm do sítio**. Na amostra cega é a mesma coisa, medida no raster: grupo de tinta da
cabeça em x = 14,0–16,9 mm, com a margem direita a 143,9 mm.

**Como reproduzir:**

```
.venv\Scripts\python.exe -c "import pymupdf; d=pymupdf.open('benchmarks/reports/proofsheet.pdf');
 print([(round(s['bbox'][0],1),s['text']) for i in (10,11,12) for b in d[i].get_text('dict')['blocks']
        if b['type']==0 for l in b['lines'] for s in l['spans'] if s['bbox'][1]<14])"
```

**Nas referências:** quatro páginas do conjunto trazem fólio numa margem lateral, e **as
quatro acertam a paridade**:

| referência | fólio impresso | paridade | lado | ✔ |
|---|---|---|---|---|
| Quality Chess (blind3 A) | 149 | ímpar | direita | ✔ |
| Quality Chess (blind5 F) | 181 | ímpar | direita | ✔ |
| Nunn (blind5 D) | 180 | par | esquerda | ✔ |
| Everyman/Aagaard (blind5 E) | 218 | par | esquerda | ✔ |
| Gambit (blind5 C) | 147 | — | centrado ao pé | n/a |
| **nossa** | **44 / 45 / 46** | — | **esquerda / esquerda / esquerda** | **✘ na 45** |

**Por que reprova.** Três razões, e nenhuma é de gosto.

1. **§2.1, à letra.** É um defeito que apontei na nossa e que não pude apontar em nenhuma das
   cinco, e foi o **primeiro** dos quatro sinais pelos quais eu a identifiquei. A §2.1 diz que
   identificar a nossa por ser pior é reprovação automática. Dos quatro sinais, retirei dois e
   arrumei um como autoria. **Este fica, e é tipográfico.**
2. **É sistemático, não é um acaso do arnês.** Não depende de que número o `build_blind`
   escolheu: a corrida 44/45/46 está dentro do PDF entregue e um livro de 200 páginas sairia
   com 100 fólios na lombada. Não é «com alguns ajustes» — são metade das páginas.
3. **É a convenção mais elementar da mobília de uma página de livro**, é visível sem
   instrumento nenhum, e é a primeira coisa que um editor confere numa prova. A pergunta da
   §1 da carta — *«um enxadrista profissional que edita material para publicação trocaria a
   ferramenta dele por esta?»* — responde-se sozinha: ele devolveria a prova.

**Que não é problema de outra frente:** o vocabulário existe no modelo do produto
(`src/caissa/core/model/blocks.py`: `PageGeometry.mirror_margins = True`,
`SectionBreak.different_odd_even`), mas **nenhum compositor os lê** — grep em `src`, `tools`
e `tests` dá apenas a declaração, o round-trip do exportador HTML e um gerador de testes. O
compositor que produziu a amostra e a folha é o da F7, e o `decorate` que escreve o fólio é
código da F7.

**É a única coisa que bloqueia.** Não peço mais nada.

---

## Defeitos não bloqueantes

1. **`move → body` continua a sair a duas alturas na mesma página** — o não bloqueante nº 1
   do ciclo 5, que o ciclo 7 declara honestamente como *«melhorado e medido, não fechado»*.
   Como o `gapaudit.py` está morto, medi-o por dois caminhos independentes:
   * a auditoria do próprio compositor, que lê a composição e não uma tabela —
     `Composition.unequal_gaps()` → **`mareco: {'move->body': [0, 1, 1, 1, 1]}`**,
     **`rios: {}`**;
   * o raster entregue (`critique/c8/mb.py`): na coluna esquerda o par leva **+3,30 mm** de ar
     cinco vezes; na direita, a **y = 811 px**, leva **+0,89 mm**. Diferença **2,4 mm**, quase
     uma linha. Recortei as duas a 3× e vê-se: `21.♗xh7†!+−` / `Checkmate cannot be avoided.`
     colados, contra `13…bxc5?!` / `Black obtains a terrible version…` com uma linha de ar.

   Melhorou de verdade desde o ciclo 5 (era 2,00 casas contra 1,00; é 1 contra 0), e a página
   portuguesa já não tem nenhuma classe desigual. Carta §3.3: *«Espaçamento inconsistente
   entre elementos equivalentes.»*

2. **Figurinos em linha os mais leves das seis** (corpo a 134,2 de cinza médio contra 122,2 da
   segunda mais leve). Retirei a acusação acima; fica o número.

3. **`build_blind.render_ours` não emite amostra em nenhuma das duas fontes** (`mareco` e
   `rios`, ambas 52/53 nas duas colunas). Não é defeito de página — os pés fecham a 0,000 mm e
   duas referências fazem pior — mas o ciclo 7 entregou o arnês cego partido e não o reportou.

4. **Dois pés abertos de espécime**, p3 76,4 mm e p8 116,0 mm, preço declarado de manter as
   secções com o que titulam. Confirmado a 400 DPI. Não é página de livro.

5. **Uma linha de meio de parágrafo a 0,89 da medida** (`Black obtains a terrible version of
   the hanging`), enquanto o critério que o R1 pediu era ≥ 0,94. O `unjustified2.py` conta
   **0** linhas com justificação abandonada nas duas fontes — o R1 está fechado como foi
   escrito — mas a linha mais funda ainda fica 5 pontos percentuais abaixo do alvo do texto
   do R1.

6. **O conteúdo de `book_source_mareco` contradiz-se**: `Final remarks` diz *«Black lost this
   game in one move, with 17…♘d7»*, lance que não aparece em lado nenhum da página e que
   contradiz o diagnóstico do lance 13 dois parágrafos acima; e `A sharper example` salta do
   lance 14 para o 21 sem ponte nem posição. É autoria, não composição — a mesma categoria em
   que o ciclo 5 arrumou os erros de `book_source_rios` — mas é a página que nos representa,
   e foi um dos quatro sinais pelos quais eu a identifiquei.

---

## O que verifiquei e está sólido

Por dever da §5.5, e é muito.

* **A vantagem da §5.1 está cumprida, e é maior do que foi alegada.** 6,7 % a 9,1 % das
  linhas fora da banda aceitável contra 31,4 % a 52,6 % em **todas** as cinco páginas
  justificadas de **dois** conjuntos independentes — fator 3,5 a 7,9, num estimador
  independente do tamanho da amostra. A banda (1,89× / 2,14×) sobrevive a uma correção de
  sub-amostragem de 20 000 sorteios contra 7 de 8 colunas de referência a p < 0,05.
* **A alegação replica em material fresco.** Corri a regra do construtor sobre o blind5 —
  cinco livros novos, páginas inéditas, outra página nossa, caixas minhas — e passa 3 de 3
  contra as quatro que justificam, com a mesma única exceção estrutural.
* **A prova de vivacidade dispara** e deixa as cinco referências idênticas ao dígito.
* **O instrumento reporta falha.** `wordband` sai com **exit 1**. Não se auto-certifica.
* **O artefacto é o que o código produz, ao bit.** `proofsheet_rios.pdf` p1 contra uma
  recomposição do código atual: `max diff = 0`.
* **O R1 está fechado e re-medido por mim:** `0 mid-paragraph lines with justification
  abandoned` nas duas fontes, contra 5 de 37 e 4 de 42 no ciclo 5, a pior a 0,55.
* **O construtor argumenta contra si.** Reportou que perde a banda à sua própria página do
  ciclo 5; reportou que a página inglesa não ganha à Nunn; reportou que perde as três à
  Dvoretsky antes de explicar porquê; retirou uma afirmação que o projeto repetia
  («0 over/underfull»); e desmontou um instrumento do crítico em vez de discutir com o
  número. Verifiquei os quatro. Os quatro estão certos.
* **Os dois desafios ao instrumento procedem, os dois.** O `gapaudit.py` imprime o mesmo com
  a leitura do PDF apagada do ficheiro. O `1.90569pt` reproduz.
* **A geometria dos diagramas é a melhor do conjunto cego, e por larga margem:** três
  tabuleiros quadrados a 0,01 %, iguais entre si a **0,03 px**, contra 1,0–1,4 % de
  não-quadratura na Quality Chess e 1,6 px de variação entre tabuleiros da mesma página dela.
* **O pé de coluna fecha a 0,000 mm** nas quatro páginas de livro, contra 1,9 a 8,3 mm nas
  referências.
* **Dois fechos do ciclo 5 confirmados a olho:** a cabeça corrente está acentuada
  (`Capítulo 4 — peões pendentes`), e o título `2. Molduras` está na p3 com os seus seis
  espécimes por baixo.
* **A ordenação cega subiu:** 4º de 6 no ciclo 3, 3º de 6 no ciclo 5, **3º de 6 agora** contra
  um conjunto novo e com uma página nossa diferente — e desta vez as duas amostras que
  ficaram atrás da nossa não são digitalizações degradadas, é uma Gambit e uma Nunn.
* **A suíte corre:** `pytest tests/unit/typeset -q -p no:randomly` → **301 passed, 1 skipped
  em 251,43 s**, exit 0, o único skip é o do Brotli. Bate com os 302 itens recolhidos que o
  ciclo 7 declara. Não corri a suíte completa três vezes.

---

## O que especificamente precisa mudar para eu aprovar

**Um item. Nada mais. Não acrescento nenhum dos não bloqueantes à condição.**

**R5 — O fólio tem de ficar na margem exterior.**

Em `tools/typeset_proofsheet.py::compose_book_page`, a `decorate` escreve o fólio sempre em
`geometry.outer`. Tem de escolher o lado pela paridade do número impresso:

```python
number = page_number + index
x = geometry.outer if number % 2 == 0 else TRIM_W - geometry.outer
canvas.text(x, geometry.top - 6, str(number), size=3.3, fill=ink,
            anchor="start" if number % 2 == 0 else "end")
```

**Critério de aceitação, nas três páginas de livro da folha entregue (44, 45, 46) e numa
corrida de pelo menos quatro páginas gerada de propósito:** o fólio de **toda** a página par
começa a `outer` da margem esquerda e o de **toda** a página ímpar acaba a `outer` da margem
direita, medido dos spans do PDF. Hoje: 14,0 mm à esquerda nas três.

Enquanto lá estiverem, digam também se as margens ficam simétricas (`inner = outer = 14,0`)
por decisão ou por omissão. Um livro encadernado quer a interior maior que a exterior, e o
`PageGeometry` já tem os dois campos. Não é condição de aprovação — não consigo medir a
assimetria de margem nas referências porque os PNG estão cortados à mancha — mas é a mesma
linha de código.

Se preferirem fechar de vez, `src/caissa/core/model/blocks.py` já declara
`PageGeometry.mirror_margins` e `SectionBreak.different_odd_even` e **nenhum compositor os
lê**. Ligar o compositor da F7 a esses dois campos fecha o R5 e fecha a lacuna do modelo ao
mesmo tempo.

---

## Nota final, sobre rigor e obstrução

Este é o oitavo ciclo e a carta avisa nos dois sentidos. Digo onde caio e porquê.

**A condição que estava em aberto está cumprida.** A vantagem que a §5.1 exige é real,
reproduzi-a três vezes, o portão dispara quando sabotado, o artefacto é bit-idêntico ao que
o código produz hoje, e — o que nenhum ciclo tinha feito — ela **replica num conjunto de
cinco livros que ninguém tinha medido, com outra página nossa e com caixas desenhadas por
mim antes da revelação**. Testei também a objeção óbvia que ninguém tinha testado, a de que
a banda é um artefacto de medirmos menos linhas, e a vantagem sobrevive; e no processo
descobri que a estatística mais forte é a que o construtor pôs em terceiro lugar. Se o
veredito dependesse só disso, era APROVADO, e digo-o assim.

**Reprovo por uma coisa, e é uma coisa que não estava na lista de ninguém porque ninguém
tinha olhado.** Não é uma métrica, não é uma tolerância, não é uma discussão de instrumento:
a página 45 da folha entregue leva o número junto à lombada, as quatro referências com fólio
lateral acertam a paridade, e foi o primeiro dos quatro sinais pelos quais eu identifiquei a
nossa amostra num teste que foi cego. A §2.1 não me dá margem nisso, e a §5.3 diz para não
negociar. Das outras três coisas pelas quais a identifiquei, retirei duas depois de medir as
referências e arrumei a terceira como autoria — o que reduz a lista a este item e é
exatamente o que o enunciado pediu: **nomeá-lo, e só a ele**.

São duas linhas de código, e é o único ponto entre este relatório e a aprovação.

---

```
VEREDITO: REPROVADO
CICLO: 8
FRENTE: F7 (Tipografia)
```

**A razão, numa linha:** a vantagem que faltava está provada, replicada num conjunto novo e
robusta à objeção de sub-amostragem — mas o fólio não alterna, a página 45 da folha entregue
leva o número na margem interior, as quatro referências com fólio lateral acertam a paridade,
e foi por aí que eu identifiquei a nossa amostra num teste cego.
