# F7 — Crítica adversarial, ciclo 3

```
VEREDITO: REPROVADO
CICLO: 3
FRENTE: F7 (Tipografia)
```

> A Fase 1 abaixo foi escrita e gravada **antes** de `GABARITO.json` ser aberto; a
> revelação está marcada no ficheiro. O veredito acima é o mesmo que consta no fim,
> depois de todas as medições.

---

## Nota de procedimento — o teste cego não foi cego para mim, e digo por quê

A coordenação mandou-me ler `docs/quality/F7_CRITIQUE_C1.md` **antes** da Fase 1. Esse
documento **cita literalmente o texto da nossa página**: *"Black cannot maintain his
hanging pawns in the ideal c5-d5 position"*, *"compare the game Vitiugov – Bologan"*,
`14.♘b3!`, `After 13.dxc5`. A `amostra_E` reproduz essas frases palavra por palavra. A
identificação foi **de graça** — não custou uma medição.

Registo isto como falha do arnês (P7 do ciclo 1 fechou o vazamento de *pixels*, não o de
*conteúdo*): enquanto a página-fonte de exemplo for a mesma que o crítico anterior
transcreveu, nenhum crítico que leia o histórico pode fazer a Fase 1 às cegas. **Correção
para o ciclo 4: gerar a amostra a partir de uma partida que nunca apareceu em nenhum
documento de qualidade.**

O que isso invalida e o que não invalida:

* **Invalida** o meu "palpite real × gerado" para a amostra E. Está declarado abaixo como
  conhecido de antemão.
* **Não invalida** a ordenação. A ordenação abaixo foi construída sobre nove grandezas
  medidas, script a script, e cada posição está justificada por número. A pergunta da
  carta §2.1 que ainda tem sentido — *"consegue apontar nela algum defeito que não aponte
  também nas referências?"* — foi respondida por medição, não por reconhecimento.

Todas as medidas são minhas, por scripts em `benchmarks/reports/critique/c3/`
(`basic.py`, `scan.py`, `feet2.py`, `grid2.py`, `vgaps.py`, `wordspace.py`, `hyph.py`,
`boards2.py`, `stroke2.py`, `squares2.py`, `coords.py`, `clusters.py`, `repeat.py`).
Amostras a 200 DPI: **1 px = 0,127 mm**, **1 pt = 2,778 px**. Larguras de traço medidas
por **FWHM com interpolação sub-pixel**, não por limiar — é a única forma justa de
comparar uma aresta vetorial com uma aresta de tinta espalhada.

### A assimetria vetor × digitalização: menor do que a coordenação supôs

O enunciado diz que *"toda referência aqui é uma digitalização de livro impresso"*. **É
falso para a amostra B.** Prova (`repeat.py`): comparei todas as casas escuras vazias de
tabuleiros **diferentes** da mesma página, pixel a pixel.

| Amostra | menor \|Δ\| médio entre casas escuras de tabuleiros distintos | leitura |
|---|---|---|
| A | 20,29 | digitalização |
| **B** | **0,00 (máx \|Δ\| = 0)** | **render digital, não digitalização** |
| C | 10,80 | digitalização |
| D | 18,25 | digitalização |
| **E** | **0,00 (mediana 0,00)** | render digital |

Some-se: as seis amostras têm fundo de papel **255 exato** e `neutral_frac = 1,0000` — as
quatro digitalizações já vieram limpas e neutralizadas. Sobra ganho de tinta, irregularidade
de glifo e esquadro.

**Quanto a assimetria moveu a ordenação: pouco, e digo onde.** Ela move dois números e
mais nenhum: (a) o peso de moldura da amostra A (1/53–1/79 medido; sem o espalhamento de
tinta estaria perto de 1/100) e (b) o esquadro dos tabuleiros de C (410×406 px). Descontei
os dois — A não caiu por causa da moldura e C não subiu por causa do esquadro. As
grandezas que decidiram a ordem — pé de coluna, grade de linha de base, buraco vertical
máximo, linha mais frouxa, unidade da cabeça de partida, consistência de notação — são
**imunes ao scanner**: medem posição relativa e decisão de composição, não densidade de
tinta. E B, que é vetorial como nós, **ficou em último**. Se a limpeza vetorial bastasse
para ganhar, B não estaria lá.

---

## FASE 1 — Comparação às cegas

**Esta secção inteira foi escrita ANTES de abrir `GABARITO.json`.**

### As nove grandezas, medidas

| Grandeza | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| Página (mm) | 132,6×215,9 | 215,9×279,4 | 160,9×228,6 | 147,3×215,4 | 160,9×228,6 | 129,2×190,9 |
| Calha (mm) | 14,0 | 26,9 | 4,6 | 4,8 | 6,0 | 4,7 |
| **Desnível do pé de coluna (mm)** | 0,00 | **9,53** | 0,76 | **0,00** | **0,00** | 0,64 |
| Desnível do topo (mm) | 0,38 | 7,62 | 0,00 | 0,38 | 0,64 | 0,13 |
| **Grade de linha de base, resíduo máx. (pt)** | — | 1,95–3,35 | **0,35** | **0,27** | 1,33–2,71 | **0,26** |
| **Maior vão texto-a-texto (entrelinhas)** | — | 3,04 | 1,38 | 1,41 | **1,67** | 1,18 |
| **Linha mais frouxa (× espaço nominal)** | — | 3,8 | 2,19 | 2,79 | **3,00** | 1,60 |
| Moldura, razão largura/traço (FWHM) | 1/53–1/79 | 1/157–1/167 | 1/127–1/137 | 1/131–1/144 | 1/103–1/104 | — |
| Espalhamento da moldura na mesma página | 1,50× | 1,07× | 1,08× | 1,10× | **1,01×** | — |
| Δcinza casa clara/escura | 85–110 | 41 | 64–68 | 57 | 54–58 | — |
| Corpo da coordenada ÷ casa | (sem) | 0,465 | 0,332–0,369 | (sem) | 0,375–0,395 | — |
| Figurino ÷ glifos vizinhos (negrito) | — | **0,73** | — | — | **0,85–1,00** | — |
| Hifenações em fim de linha | — | 0 % | 3–11 % | 0–3 % | 0–3 % | 9–13 % |
| Escadas de hifenização | — | 1 | 1 | 1 | 1 | 1 |

### Ordenação, melhor para pior

| Amostra | Posição | Justificativa |
|---|---|---|
| **F** | **1º** | O ritmo mais firme do conjunto. Grade de linha de base de **9,997 pt** com resíduo máximo de **0,263 pt** sobre 45 linhas em cada coluna (rms 0,117 pt) — e é uma digitalização, o que significa que a grade real é ainda mais apertada. Justificação a mais uniforme das seis: linha mais frouxa a **1,60×** o espaço nominal, **zero** linhas acima de 2×. Maior vão texto-a-texto **1,18 entrelinhas**. Pé das colunas a 0,64 mm. Aspas curvas corretas (`‘square’`). |
| **C** | **2º** | Grade de 11,983 pt com resíduo **0,353 pt**; pé a 0,76 mm; vão máximo 1,38 entrelinhas; linha mais frouxa 2,19×. É a única amostra que compõe **símbolos de avaliação de fonte de xadrez de verdade** (`±`, `⩱`, `⩲` em `22.♖g3±`, `24.f4±`, `22.♕xf4⩱`). A unidade cabeça-de-partida está intacta: nome / régua escocesa embutida na largura do nome / `Shanghai 2001` a **4,0 mm** da régua. Coordenadas a 0,33–0,37 da casa. |
| **D** | **3º** | Pé a **0,00 mm**; grade de 11,982 pt com resíduo **0,268 pt**; dois diagramas de 45,97 mm idênticos ao pixel; ausência de coordenadas aplicada de forma consistente. Perde para C na justificação (**2,79×**, três linhas acima de 2,5×) e nas margens, apertadíssimas (6,5 mm de conteúdo à borda inferior). |
| **E** | **4º** | **A mecânica é a melhor do conjunto; as decisões de composição são as piores das quatro melhores.** A favor: pé de coluna a **0,00 mm**; três tabuleiros de **405×405 px exatos** com moldura de **3,91/3,93/3,91 px** (espalhamento 1,01× — o menor medido); Δcinza 54–58, dentro da faixa das referências; coordenada a 0,375–0,395 da casa, dentro da faixa; figurino a **0,85–1,00** da cor dos vizinhos, **melhor que a única referência comparável (B, 0,73)**; uma hifenização em 52 linhas, zero escadas. Contra — e cada item destes **não aparece em C, D nem F**: (a) **9,7 mm de branco entre a régua da cabeça de partida e `Osasco 2012`**, contra 4,0 mm em C na mesma construção: a justificação vertical rasgou uma unidade semântica; (b) **o mesmo lance composto de duas maneiras na mesma página** — `14.♘b3!` com figurino no corpo, `After 14.Nb3` com `N` de ASCII na legenda; (c) **duas convenções de avaliação na mesma página** — `16.e3±` com glifo real, `21.♗xh7†!+−` e `25.♕g4+−.` com o par ASCII `+`/`−`; (d) **as linhas de continuação de uma sub-variante saem recuadas para a margem da linha principal** (`25.♖h8‡` e `1–0` a recuo 0 debaixo de um bloco recuado a 1 em) — o leitor lê a continuação como lance novo; (e) essa mesma sub-variante justificada a **3,00×** o espaço nominal da página e a **3,7×** o espaço da linha em negrito imediatamente acima (27 px contra 6–8 px, medidos glifo a glifo em `clusters.py`); (f) **`A sharper example, same family`** — linha centrada, em romano de corpo, sem pontuação final: nem título, nem parágrafo; (g) o figurino em negrito é engordado por **traçado do contorno**, o que fecha os contra-punções — a fenda da mitra do bispo está preenchida a 8,6 pt (`z_E_bishop.png`, 14×). |
| **A** | **5º** | Página de galeria: seis diagramas, seis números, uma cabeça corrente, uma legenda italiana (`Black to move`) pendurada sob **um** diagrama. A grade de tabuleiros é regular (passo de fileira 448 e 453 px). Não há corpo de texto, não há hierarquia, não há aparelho tipográfico para julgar — fica em 5º por **ausência de matéria julgável**, não por defeito. Descontando o ganho de tinta, sobra um defeito real: a cobertura da casa escura varia de **0,323 a 0,424** entre diagramas da mesma página. |
| **B** | **6º** | O pior conjunto de **decisões** — e não é uma digitalização, é um render digital como o nosso, portanto sem álibi. Pé das colunas a **9,53 mm** (12× o pior das outras quatro referências); topos a 7,62 mm; **dois buracos de 20,4 mm e 19,6 mm** (3,0 entrelinhas) entre blocos de texto; linha mais frouxa a **3,8×**; **nenhuma grade de linha de base** (resíduo 1,95–3,35 pt); cabeçalho de partida numa **caixa cinza de cantos arredondados com sombra projetada** — decoração de editoração, não de livro; figurino a **0,73** da cor do negrito em que está; as coordenadas mais gordas do conjunto (0,465 da casa). A favor: tabuleiros consistentes e o tom de casa mais leve (Δ41). |

### Palpite real × gerado (antes da revelação)

| Amostra | Palpite | Evidência |
|---|---|---|
| A | **real** | Nenhuma casa escura igual a outra (min \|Δ\| 20,29); tabuleiros de 320 e 321 px na mesma página; passo de fileira 448 e 453 px; arestas de glifo esfarrapadas. Nenhum renderizador produz isso. |
| B | **real, mas PDF nativo — não digitalização** | Casas escuras de tabuleiros diferentes **bit a bit idênticas** (máx \|Δ\| = 0), papel 255 exato, zero grão: é vetorial. Mas a tipografia não é a nossa: reticências de três pontos, `+` para xeque, caixa com sombra, coordenada a 0,465 da casa, página exatamente 8,5×11 in, figurino a 0,73. O nosso motor não produz nenhuma dessas. |
| C | **real** | Face humanista com ligadura `Th`, espalhamento de tinta, tabuleiros **fora de esquadro** (410×406 e 412×407 px), min \|Δ\| 10,80 entre casas. |
| D | **real** | Ganho de tinta forte e desigual, min \|Δ\| 18,25, glifos inchados e irregulares. |
| **E** | **gerada** — *e eu já sabia, ver a nota de procedimento* | Prova de pixel independente do vazamento: **todas** as casas escuras dos três tabuleiros são idênticas (mediana \|Δ\| = 0,00), os três tabuleiros medem 405×405 px exatos e as três molduras 3,91/3,93/3,91 px de FWHM. Times New Roman de ponta a ponta. Zero grão de papel. |
| F | **real** | Espalhamento de tinta, arestas irregulares; e a grade de 9,997 pt sobrevive ao scanner, o que só acontece quando a grade original é rígida. |

---

<!-- REVELAÇÃO ABAIXO DESTA LINHA -->

### Identidade revelada

`GABARITO.json`:

| Amostra | Origem | Minha posição | Meu palpite |
|---|---|---|---|
| A | referência — Batsford p112 | 5º | real ✔ |
| B | referência — Dvoretsky 2025 p175 | 6º | real (PDF nativo) ✔ |
| C | referência — Quality Chess p139 | 2º | real ✔ |
| D | referência — Everyman/Aagaard p175 | 3º | real ✔ |
| **E** | **nossa — proofsheet p11** | **4º de 6** | gerada ✔ (mas ver a nota de procedimento) |
| F | referência — Gambit p94 | 1º | real ✔ |

**A nossa ficou em 4º de 6 — fora das duas últimas posições.** A primeira das três
condições que o crítico do ciclo 1 pôs está cumprida, e digo isso sem reservas: é uma
subida de 5º/6º/7º de sete para 4º de seis, contra um conjunto mais forte.

**O que a denunciou, em pixels, sem contar o vazamento de conteúdo:**

1. **Repetição perfeita.** Todas as casas escuras dos três tabuleiros são idênticas
   (mediana \|Δ\| = 0,00); os três tabuleiros medem 405×405 px; as três molduras medem
   3,91 / 3,93 / 3,91 px de FWHM. B tem a mesma propriedade, portanto isto sozinho **não**
   a separava do conjunto. Bom sinal para o arnês.
2. **A unidade da cabeça de partida rasgada** — 9,7 mm entre a régua e `Osasco 2012`,
   contra 4,0 mm em C, que compõe exatamente a mesma construção. Isto é uma decisão nossa.
3. **Duas notações para o mesmo lance na mesma página** — `14.♘b3!` / `After 14.Nb3`.
4. **Duas convenções de avaliação na mesma página** — `16.e3±` (U+00B1) e `21.♗xh7†!+–`
   (U+002B + U+2013). C compõe `±`, `⩱` e `⩲` todos como glifos únicos.
5. **Continuações de sub-variante recuadas para a margem principal** — medido no PDF: o
   bloco `22…g6 23.♕xh7†! …` está a 9,46 pt de recuo e a sua continuação `25.♖h8‡` a
   **0,00 pt**. Idem `1–0` sob `Or 23…♘e7 …`.

**A carta §2.1, segunda condição:** *"você não pode ter apontado nela nenhum defeito que
não tenha apontado também nas outras."* **Falhou.** Os cinco itens acima, mais a linha a
3,00× o espaço nominal e os contra-punções fechados do figurino em negrito, são defeitos
que apontei em E e **não** em C, D nem F.

**A vantagem clara e mensurável exigida pelo ciclo 1: não existe.**

| Candidata | Nossa | Melhor referência do conjunto | Veredito |
|---|---|---|---|
| Pé de coluna | 0,00 mm | **D 0,00 mm**, A 0,00 mm, F 0,64 mm, C 0,76 mm | **empate** |
| Grade de linha de base | 28 linhas, resíduo 0,000 pt | **F: 45 linhas por coluna, resíduo 0,263 pt** | **perdemos** |
| Registo através da calha | 9 de 22 linhas da coluna esquerda (41 %) | **F: 45 de 45 (100 %), erro de fase mediano 0,100 pt** | **perdemos** |
| Ocupação da grade | 45 % (esq.) / 43 % (dir.) | F: 100 % | **perdemos** |
| Figurino ÷ vizinhos | 0,90–1,00 | B 0,73 | **ganhamos** (contra uma referência só) |
| Consistência de moldura na página | 1,01× | B 1,07× | margem sem significado (três diagramas do mesmo tamanho) |

Carta §5.1: *"Empate não é aprovação."* O ciclo 1 nomeou o pé de coluna como a candidata
natural e disse *"nenhuma das quatro referências acerta melhor que 0,0 mm"*. Neste
conjunto **duas** acertam 0,00 mm. E a propriedade que o relatório apresenta como
exclusiva — a grade de linha de base com registo entre colunas — **é feita melhor por uma
página digitalizada da Gambit**, com 45 linhas por coluna a 100 % de registo contra as
nossas 28 a 41 %.

---

## FASE 2 — Os doze bloqueantes, re-medidos por mim

Nenhum número abaixo veio do relatório. Scripts em `benchmarks/reports/critique/c3/`.

| # | Alegação do ciclo 2 | A minha medida | Veredito |
|---|---|---|---|
| 1 | P1: 0 de 12 páginas com conteúdo abaixo da margem, pior 0,00 mm | `pdfbottom.py` sobre o PDF entregue: 12/12 dentro; folga mínima **0,51 mm** (p10–12); pior transbordo **0,00 mm** | **CONFIRMADO** |
| 2 | P1: três temas, mesma lista de blocos | camadas de texto de p10/p11/p12 **idênticas** após remover o fólio: 325 spans cada, mesmo x, y, corpo e string | **CONFIRMADO** |
| 3 | P1: cabeça de lance duplicada corrigida | zero tokens de lance repetidos em p10/11/12 | **CONFIRMADO** |
| 4 | Pé de coluna 0,000 mm | p10/11/12 = **0,000 mm**. Mas a **própria ferramenta do construtor** imprime `p2 44,073 mm`, `p4 30,750 mm`, `p9 5,800 mm`, `p8 3,944 mm` — e o relatório mostra uma tabela de três linhas | **CONFIRMADO em 3 de 12 páginas; como propriedade do documento, REFUTADO** |
| 5 | Grade: 28 linhas, uma grade de 10,406 pt, zero fora; "nenhuma referência faz isto" | Reproduzi com o filtro do próprio teste: **28 linhas de corpo, 0 fora**. O filtro `size == BODY_PT ± 0,2` deixa **76 dos 325 spans** de fora (coordenadas 11,08 pt, legendas 7,05 pt, fólio 9,35 pt). A exclusividade cai: **F** ajusta 9,997 pt com resíduo máximo **0,263 pt** sobre 45 linhas/coluna; C 11,983 pt / 0,353 pt; D 11,982 pt / 0,268 pt. A 200 DPI um pixel vale 0,36 pt: as três estão **na grade dentro do erro de medição** | **CONFIRMADO para a nossa página; exclusividade REFUTADA** |
| 6 | P2: 49–56 % dos pixels da cabeça da seta | reproduz exatamente (126/256, 306/576, 649/1156) | **número CONFIRMADO** |
| 7 | P2: marcas fechadas | **REFUTADO — bloqueante nº 1.** O recorte branco decapita as peças: na p5 os peões de b2 e f2 ficam com a cabeça **separada** do corpo; a base do peão de c5 é substituída pela ponta da seta; o cavalo de d2 leva uma mordida branca. No LaTeX a ponta sobre o peão preto de g7 é cinza 63 sobre preto = **1,99:1** | **REFUTADO** |
| 8 | P2: 16/16 rótulos `inside` legíveis | 16/16 legíveis, sim. Mas o algarismo **2 continua desenhado dentro do peão de a2 e continua a partir-lhe o contorno** — a frase é do ciclo 1 e ainda descreve o artefato — e as chapas opacas de `c`, `d`, `f`, `g` **mordem entalhes** na torre de c1, na dama de d1, na torre de f1 e no rei de g1; o próprio `2` sai cortado pela linha da fileira | **CONFIRMADO à letra, REFUTADO na substância** |
| 9 | P2: destaque preserva o xadrez, 63 de 65 | reproduz (book 63,0 de 65,0). Mas `test_a_highlight_keeps_the_chequer` **salta** o tema `hatched` (`if theme.light == theme.dark: continue`), e a ferramenta mostra `hatched` a **113,0 de 134,9 = 84 %**, abaixo dos 90 % exigidos nos outros temas — e mede 255,0 contra 120,1 de matiz nesse tema, contrariando a justificativa dada | **CONFIRMADO com isenção não declarada** |
| 10 | P3: 55 molduras, 1/101,3 a 1/122,1, espalhamento 1,21× | reproduz exatamente. Verificação independente por FWHM sub-pixel no raster da página de livro: **1/103,5** contra o vetor 1/103,0 | **CONFIRMADO** |
| 11 | P3: menor coordenada 7,03 pt, suprimida abaixo de ~28 mm | 7,03 pt confirmado; supressão no tabuleiro de 20 mm confirmada. **Mas a folha imprime `Pretas jogam` a 3,40 pt na p4** — menor que os 3,92 pt reprovados no ciclo 1. `test_nothing_in_the_proof_sheet_prints_type_below_the_floor` filtra `len(text)==1 and text in "abcdefgh12345678"`: só olha coordenadas | **CONFIRMADO para coordenadas; o nome do teste é falso** |
| 12 | P3: hachura 31,4–31,9 %, passo 0,90 mm | Na página **entregue** (p10, tabuleiro 143,02 pt), cobertura por **área** numa casa escura vazia: **0,277 / 0,280 / 0,283**. O método do construtor lê **uma linha de varredura**; na mesma casa, vinte linhas dão **0,254 a 0,320**. O 0,318 relatado é o topo desse intervalo. Referências pelo mesmo método de área: A 0,33/0,43, B 0,16, C 0,25/0,27, D 0,22 | **CONFIRMADO na substância (0,28, dentro da faixa); o 0,318 é artefato do método de linha única** |
| 13 | P4: figurino 0,98 / 0,99 | ferramenta reproduz. Medida independente minha no raster cego, quatro figurinos numa linha em negrito: **0,90 / 0,90 / 0,98 / 1,00**. Referência B: **0,73** | **CONFIRMADO** |
| 14 | P5: 1 divergência entre exportadores | A ferramenta conta 1 porque compara **duas passagens de lances**. Fora do que ela olha: (a) glifo de reticências (admitido); (b) **espaço após as reticências na cabeça corrente: 5,12 pt no LaTeX, 0,00 pt no SVG**; (c) **xeque na legenda: `After 21.Bxh7†.` vs `After 21.Bxh7+`**; (d) travessão da legenda U+2014 vs U+2013; (e) **71 spans em negrito no SVG contra 7 no LaTeX — o LaTeX não compõe nenhuma linha de lances em negrito** | **REFUTADO — pelo menos 5** |
| 15 | P5: um só desenho de peça | recompilei do zero: `Chess-Alpha` e mais nada de xadrez | **CONFIRMADO** |
| 16 | P5: `\chapter*` fora do `multicols` | confirmado na página compilada; o buraco de 25 mm sumiu | **CONFIRMADO** |
| 17 | P6: 18 de 18 famílias | as 18 chaves `VERIFIED` aparecem e são **desenhadas**, em p1–2 e p6–7 | **CONFIRMADO** |
| 18 | P6: português acentuado, tudo por `prepared()` | nas 12 páginas: **zero** U+0027, **zero** U+0022, **zero** reticências de três pontos, zero espaço duplo, zero espaço antes de pontuação | **CONFIRMADO** |
| 19 | 238 passam / 1 pula | **três execuções**: 238/1 em 131,41 s, 122,94 s, 158,27 s (mediana 131,41 s) | **CONFIRMADO** |
| 20 | LaTeX: 0 caixas over/underfull, 162 702 bytes | recompilei em diretório limpo, duas passadas, exit 0, **162 702 bytes**, **0 over/underfull**. **Aviso não declarado:** `Font shape 'T1/lmss/m/up' undefined … defaults substituted` | **CONFIRMADO com substituição de fonte não declarada** |
| 21 | (não alegado) reprodutibilidade | Gerei a folha **duas vezes** com `--out` para diretórios de rascunho: as camadas de texto das duas são idênticas **e idênticas à do artefato entregue**. Só o carimbo de tempo difere | **CONFIRMADO — e conta a favor** |

**Contagem:** 21 verificações — 14 confirmadas limpas, 4 confirmadas com ressalva, 3
refutadas.

---

## FASE 3 — O que o ciclo 2 não admitiu

O §5 do relatório lista dez itens abertos. Nenhum dos quinze abaixo está nessa lista.

### 3.1 A justificação vertical comprou o pé de coluna com buracos, e a conta não foi apresentada

O relatório admite **um** vão: *"A folha de prova tem um vão de 21,5 mm no pé da página 8 …
As outras onze páginas fecham com 0,4 a 8,4 mm de folga."* Medi os vãos **internos**, de
largura de página, nas doze (união de todas as caixas de desenho e de texto, excluindo o
fundo do papel):

| Página | Vãos internos ≥ 8 mm | Folga no pé |
|---|---|---|
| 1 | 15,9 · 12,0 | 22,4 |
| 2 | 20,5 · 12,0 | 17,8 |
| 3 | 17,7 · 8,1 | 22,3 |
| 4 | 18,5 · 15,1 | 17,8 |
| 5 | 12,6 | 17,7 |
| 7 | 11,5 | 24,4 |
| **8** | **35,6 · 27,8** | **37,5** |
| **9** | **30,5** | 21,7 |
| 6, 10, 11, 12 | — | 21,3 / 16,4 / 16,4 / 16,4 |

**Nove das doze páginas** carregam um vão interno ≥ 8 mm. A página 8 tem
**35,6 + 27,8 = 63,4 mm de buraco interno** mais 21,5 mm além da margem: **84,9 mm de
branco morto numa página de 228,6 mm — 37 % da altura**. O que ela contém é um tabuleiro,
uma legenda, um título de seção e um parágrafo de três linhas.

O título `8. Tamanhos — tema "hachurado"` fica **separado do seu próprio parágrafo de
abertura por 27,8 mm**. Um título desligado do texto que titula é o defeito de espaçamento
da carta §3.3 na sua forma mais direta. Este é o preço do pé de coluna a 0,000 mm, e é o
número que falta no relatório.

### 3.2 Duas seções numeradas 8

`p7: "8. Tamanhos — tema “cinza neutro”"` e `p8: "8. Tamanhos — tema “hachurado”"`.
Não há seção 9. As três páginas de livro não têm número de seção nenhum.

### 3.3 Tipo a 3,40 pt na folha de prova

`p4`, espécime `text` do indicador de lance: **`Pretas jogam` a 3,40 pt**. O ciclo 1
reprovou 3,92 pt. A folha do ciclo 2 imprime **13 % menor** que o defeito reprovado, na
mesma folha onde o piso de 5,5 pt é anunciado.

### 3.4 A legenda de 90 mm não está alinhada com o tabuleiro de 90 mm

| Página | Legenda | x da legenda | x da moldura | erro |
|---|---|---|---|---|
| 9 | `20 mm` | 39,7 | 39,7 | 0,0 |
| 9 | `40 mm` | 114,7 | 114,7 | 0,0 |
| 9 | `60 mm` | 246,3 | 246,3 | 0,0 |
| **8 e 9** | **`90 mm`** | **39,7** | **66,0** | **26,3 pt = 9,3 mm** |

Três legendas assentam na aresta esquerda do seu tabuleiro; a quarta está 9,3 mm à
esquerda da sua. Carta §3.3: *"Alinhamento óptico errado."*

### 3.5 O teste que a página de tamanhos existe para fazer deixou de ser possível

A legenda da seção diz: *"20, 40, 60 e 90 mm. O peso do traço e o corpo das coordenadas têm
de sobreviver aos quatro."* No ciclo 1 os quatro estavam na mesma página. Agora o
compositor por fluxo põe 20/40/60 numa página e o de 90 mm na seguinte — **duas vezes**
(seção 8 "cinza neutro" p7→p8; seção 8 "hachurado" p9→p8). Os quatro tamanhos já não se
veem juntos: a comparação para a qual a página foi construída deixou de existir.
É uma **regressão** introduzida pela correção do P1.

### 3.6 `+–` é sinal de mais mais **meia-risca**, não sinal de menos

Códigos extraídos do PDF:

* `16.e3±` → **U+00B1**, correto.
* `21.♗xh7†!+–` → **U+002B U+2013**.
* `25.♕g4+–.` → **U+002B U+2013**.

U+2013 é EN DASH. O sinal de menos é U+2212, e **Times New Roman tem-no** (verifiquei o
`cmap` de `times.ttf`: `U+2212 present=True`). Não é limitação de cobertura de glifo — que
é a justificação que o §5 nº 9 dá para `⩲ ∓ ⩱` — é erro de composição, e é o defeito que a
carta §3.3 nomeia literalmente: *"Traço errado."* Na mesma página, uma avaliação sai como
glifo único correto e a outra como par falsificado.

### 3.7 As continuações de sub-variante saem recuadas para a margem principal

Coordenadas do PDF, p10, coluna direita, margem = 0,00:

| y | recuo | linha |
|---|---|---|
| 495,65 | 0,00 pt | `21…♘xh7 22.♗f6 ♕xc4` (linha principal) |
| 506,05 | **9,46 pt** | `22…g6 23.♕xh7†! ♔xh7 24.♖h3† ♔g8` (sub-variante) |
| 516,46 | **0,00 pt** | `25.♖h8‡` ← **continuação da sub-variante, na margem principal** |
| 526,86 | 0,00 pt | `23.♖xg7† ♔f8 24.♕h6 ♖ec8 25.♖g8†` (linha principal) |
| 537,27 | **9,46 pt** | `Or 23…♘e7 24.♗xe7 ♖dxe7 25.♕g4+–.` (sub-variante) |
| 547,68 | **0,00 pt** | `1–0` ← idem |

Um leitor de xadrez lê `25.♖h8‡` como lance novo da linha principal, porque é onde ele
está. Nenhuma das cinco referências comete isto.

### 3.8 Uma linha a 3,00× o espaço nominal, ao lado de uma a 1,0×

A linha `22…g6 23.♕xh7†! ♔xh7 24.♖h3† ♔g8` (p10, y=506) tem vãos entre palavras de
**26–28 px a 200 DPI**, medidos glifo a glifo. A linha em negrito **imediatamente acima**,
do mesmo tipo de elemento, tem **6–8 px**. Contra o espaço nominal da página (9,0 px) são
**3,00×** — mais frouxa que C (2,19×), D (2,79×) e F (1,60×).

### 3.9 A cabeça de partida e a sua linha de local ficaram a 9,7 mm uma da outra

Contra 4,0 mm em C, que compõe a mesma construção (nome / régua escocesa / local).
Recortes: `critique/c3/z_E_gamehead.png` e `z_C_gamehead.png`. A justificação vertical
trata `Osasco 2012` como bloco independente e distribui-lhe folga; ele pertence à cabeça.

### 3.10 O mesmo lance, duas notações, na mesma página

Corpo: `14.♘b3!` com figurino. Legenda: `After 14.Nb3` com `N` de ASCII. Idem
`21.♗xh7†!` / `After 21.Bxh7†.`. O `prepared()` de notação não chega às legendas.

### 3.11 No tema escuro a moldura é invisível

Raster de p12 a 200 DPI:

| | RGB | contraste |
|---|---|---|
| fundo da página | (27, 31, 35) | — |
| **traço da moldura** | **(14, 17, 20)** | **1,14:1 contra o fundo** |
| casa clara | (155, 163, 171) | 3,25:1 contra a moldura |
| casa escura | (94, 102, 110) | 2,84:1 contra o fundo |

O valor de sistema de 1/103 que o P3 padronizou **não faz nada** num dos três temas
entregues: a moldura é mais escura que o papel. Ou clareia no tema escuro, ou deixa de ser
desenhada e o degrau de tom passa a ser a regra declarada.

### 3.12 O negrito do figurino é feito fechando os contra-punções

`FIGURINE_WEIGHT_BOLD = 0,048` em traça o contorno **para dentro e para fora**. A 8,6 pt a
fenda da mitra do bispo fecha e a base vira um losango sólido (`critique/c3/z_E_bishop.png`,
14×). A razão de tinta subiu para 0,99 e o desenho perdeu a silhueta interna — a medida
melhorou enquanto o glifo piorava. Falta um segundo critério: **área de contra-punção do
figurino em negrito ÷ a do mesmo glifo em romano ≥ 0,7**.

### 3.13 O exportador LaTeX não compõe lances em negrito

71 spans em negrito no SVG, **7** no LaTeX — e esses sete são a cabeça de partida e
`Learning objective:`. A convenção que separa linha principal de prosa existe num
exportador e não no outro. `compare_exporters.py` não a vê porque compara strings, não
estrutura.

### 3.14 `T1/lmss/m/up` indefinida

`livro.log`: `Font shape 'T1/lmss/m/up' undefined … defaults substituted.` Substituição
silenciosa de fonte num entregável de tipografia, não declarada.

### 3.15 O arnês cego continua a vazar — pelo conteúdo

Ver a nota de procedimento no topo.

---

## Defeitos bloqueantes

### 1. O recorte das marcas desmembra as peças. C1 nº 4 não está fechado — está invertido.

**Onde:** `proofsheet.pdf` p5, os quatro tabuleiros; `latex/livro.pdf` p1, diagrama
inferior direito. Ampliações: `critique/c3/pf05_dfile.png`, `pf05_knight.png` (800 DPI),
`lx_arrow.png` (500 DPI).

**O que:** `KNOCKOUT_MM = 0,30` traça a marca primeiro na cor do papel. As nossas peças são
**contornos brancos**. Um recorte branco sobre um contorno branco **apaga o contorno**.

* tabuleiro `salto de cavalo`: as hastes horizontais cortam b2 e f2 e **separam a cabeça do
  peão do seu corpo** — o leitor vê uma bola solta acima de uma base decapitada;
* tabuleiro `setas retas`: a ponta c1→c5 **substitui a base do peão de c5**; a peça deixa de
  ser identificável;
* o cavalo de d2 fica com um entalhe branco onde a cauda começa;
* no LaTeX a ponta sobre o peão preto de g7 é **cinza 63 sobre preto 0 = 1,99:1**, abaixo
  dos 3:1 da WCAG 1.4.11 e abaixo do limiar que o próprio construtor exige em
  `test_a_piece_is_identified_by_its_outline_in_every_theme`.

**Como reproduzir:** `critique/c3/render.py 5 800 x.png 92 95 135 200` e
`… 5 800 y.png 245 155 420 190`; para o LaTeX, amostrar a cor da ponta (cinza 63, 8661 px).

**Por que reprova:** é textualmente o defeito do ciclo 1 — *"uma anotação que destrói a
informação que anota é pior que anotação nenhuma"* — e a métrica escolhida (pixels da cor
da seta dentro da cabeça) **sobe exatamente quando o defeito piora**. O ciclo 1 ofereceu
duas saídas; foi escolhida a que não funciona sobre peças de contorno.

### 2. `CoordinatePlacement.inside` corrompe agora as peças em vez das coordenadas.

**Onde:** `proofsheet.pdf` p4, primeiro tabuleiro. Ampliações: `critique/c3/pf04_rank1.png`
e `pf04_a21.png` (900 DPI).

**O que:** os 16 rótulos são legíveis — o critério do construtor está cumprido. Mas:

* o algarismo **`2` continua desenhado dentro do peão branco de a2 e continua a partir-lhe
  o contorno** — frase literal do defeito nº 3 do ciclo 1;
* o `2` sai **cortado** pela aresta da fileira: só a metade superior aparece;
* as chapas opacas de `c`, `d`, `f` e `g` **mordem entalhes retangulares** na torre de c1,
  na dama de d1, na torre de f1 e na coroa do rei de g1.

**Por que reprova:** carta §3.3, primeiro item visual — *"Qualquer texto cortado,
sobreposto."* Quatro peças e um algarismo. A opção continua a produzir um diagrama que um
editor não publica.

### 3. Os dois exportadores divergem em cinco pontos, não em um, e a ferramenta de medida não os vê.

| Elemento | SVG | LaTeX |
|---|---|---|
| reticências (glifo) | U+2026 | três pontos *(admitido)* |
| **espaço após as reticências na cabeça corrente** | **0,00 pt** | **5,12 pt** (1,54× um espaço de palavra) |
| **xeque na legenda do diagrama** | `After 21.Bxh7†.` | `After 21.Bxh7+` |
| travessão da legenda | U+2014 | U+2013 |
| **linhas de lances em negrito** | **71 spans** | **7 spans — nenhuma linha de lances** |

**Por que reprova:** o defeito nº 9 do ciclo 1 era *"um livro exportado nos dois sai com
duas notações diferentes"*. Continua verdade — agora nas legendas e na estrutura em vez de
na linha principal. E a alegação "visualmente idênticos" sobre as reticências é falsa por
5,12 pt medidos.

### 4. A folha de prova entrega 37 % de uma página em branco e um título separado do seu texto por 27,8 mm.

**Onde:** `proofsheet.pdf` p8 (35,6 + 27,8 + 21,5 mm), p9 (30,5 mm), e mais sete páginas com
vãos ≥ 8 mm. Números na §3.1.

**Por que reprova:** carta §3.3 — *"Espaçamento inconsistente entre elementos
equivalentes"* — e porque o relatório apresenta o pé de coluna a 0,000 mm como a conquista
do ciclo sem dizer que foi pago com isto.

### 5. Nenhuma vantagem clara e mensurável sobre as referências. (Carta §5.1, e a condição explícita do ciclo 1.)

Pé de coluna: **empate** com duas referências. Grade de linha de base e registo entre
colunas: **perdemos** para a Gambit digitalizada, que faz 45 linhas por coluna a 100 % de
registo contra as nossas 28 a 41 %. A única vantagem medida — figurino a 0,90–1,00 contra
0,73 — é contra **uma** referência, e as outras quatro não permitem a medida.

---

## Defeitos não bloqueantes

1. **Duas seções numeradas 8**, sem seção 9 (§3.2).
2. **`Pretas jogam` a 3,40 pt** na p4; o teste do piso só olha rótulos de um caractere (§3.3).
3. **Legenda `90 mm` desalinhada 9,3 mm** do tabuleiro que rotula (§3.4).
4. **Os quatro tamanhos deixaram de caber na mesma página** (§3.5).
5. **`+–` composto com EN DASH** onde U+2212 existe na fonte (§3.6).
6. **Continuações de sub-variante na margem principal** (§3.7).
7. **Linha a 3,00× o espaço nominal** ao lado de uma a 1,0× (§3.8).
8. **Cabeça de partida a 9,7 mm da linha de local**, contra 4,0 mm na referência (§3.9).
9. **`After 14.Nb3` contra `14.♘b3!` na mesma página** (§3.10).
10. **Moldura invisível no tema escuro**, 1,14:1 contra o fundo (§3.11).
11. **Contra-punções do figurino em negrito fechados** pelo traçado do contorno (§3.12).
12. **`A sharper example, same family`** — linha centrada, romana de corpo, sem pontuação:
    nem título, nem parágrafo, nem legenda.
13. **`T1/lmss/m/up` substituída em silêncio** na compilação LaTeX (§3.14).
14. **`test_a_highlight_keeps_the_chequer` isenta o tema `hatched`**, onde a própria
    ferramenta mede 84 % contra os 90 % exigidos nos outros.
15. **O conjunto cego vaza pelo conteúdo** (nota de procedimento, §3.15).
16. Indicador de lance ainda a flutuar fora da moldura, quadrado e triângulo com pesos
    ópticos diferentes *(admitido, §5 nº 5)*.
17. Cobertura de hachura a 0,25–0,26 abaixo de 35 mm *(admitido, §5 nº 2)*.

---

## O que verifiquei e está sólido

Por dever de §5.5, e porque é muito.

* **O pé de página existe e é real.** 12 de 12 páginas dentro da margem, medido por mim no
  PDF entregue. Era 5 de 10 com 70 mm de transbordo. É a correção mais importante do ciclo
  e está feita.
* **Os três temas produzem exatamente o mesmo conteúdo.** 325 spans idênticos em posição,
  corpo e string. A falha silenciosa do ciclo 1 desapareceu.
* **A folha de prova é reproduzível.** Gerei-a duas vezes em diretórios de rascunho: as duas
  camadas de texto são idênticas entre si **e idênticas à do artefato entregue**. O que está
  no disco é o que o código produz.
* **A moldura é um valor de sistema.** 55 molduras, 1/101,3 a 1/122,1, espalhamento 1,21×,
  zero fora da faixa — e a minha medição independente por FWHM no raster (1/103,5) bate com
  o vetor (1/103,0) a 0,5 %. Era 1/98 a 1/230.
* **A hachura está dentro da faixa das referências.** 0,28 de cobertura por área na página
  entregue, contra 0,16–0,43 nas quatro referências hachuradas do conjunto cego. Era 0,199,
  a mais clara de sete.
* **O figurino carrega a cor do tipo ao lado.** 0,90–1,00 medido por mim no raster cego,
  contra 0,73 da referência B. Era 0,56 e 0,43. É o número que mais melhorou.
* **As coordenadas têm piso e supressão.** 7,03 pt de mínimo; o tabuleiro de 20 mm sai sem
  coordenadas, como deve. E o corpo relativo (0,375–0,395 da casa) está dentro da faixa das
  referências (0,33–0,47).
* **O destaque preserva o xadrez** em quatro dos cinco temas com matiz, com paridade exata
  em três.
* **As 18 famílias estão desenhadas na folha**, não só listadas. Era 13½.
* **A camada de texto está limpa.** Zero aspas retas, zero reticências de três pontos, zero
  espaço duplo, zero espaço antes de pontuação, em 12 páginas de português acentuado. O bug
  do `ToUnicode` que o construtor encontrou sozinho e corrigiu era real e sério.
* **O LaTeX compila de verdade e sozinho.** Recompilei em diretório limpo: exit 0, 162 702
  bytes idênticos, **0 caixas over/underfull**, uma única fonte de xadrez.
* **A suíte roda e o número bate**, três vezes: 238 passam, 1 pula.
* **A hifenização de nome próprio está corrigida** — `Vitiugov – Bologan` inteiro na página,
  quebra num advérbio. Zero escadas de hifenização em todas as seis amostras.
* **O relatório é honesto onde é honesto.** Declara dez itens abertos, inclui números que o
  prejudicam (a cobertura a 0,25 abaixo de 35 mm, o vão da p8, a divergência das
  reticências) e admite não saber explicar a variação da contagem total de testes. Isso
  conta, e conta muito. O problema é que os itens que **não** declarou — os buracos de 35,6
  e 27,8 mm, os 44,07 mm de pé na p2, as cinco divergências entre exportadores, os 3,40 pt —
  são maiores que os que declarou.

---

## O que especificamente precisa mudar para eu aprovar

Cinco itens. Cada um com número verificável. Nada mais.

**Q1 — Marcas que não destroem peças.** Trocar o recorte por ordem de pintura: a marca vai
**por baixo** das peças, e só a **ponta** é redesenhada por cima, com contorno na cor da
casa. Critério, nos dois exportadores, no espécime da p5 e no diagrama do LaTeX:

1. nenhuma peça atravessada por uma haste pode ficar com o contorno interrompido — teste:
   componentes conectados do contorno da peça antes e depois da marca, **mesma contagem**;
2. a ponta sobre a peça de destino mede **≥ 3:1** de contraste contra a peça (hoje 1,99:1 no
   LaTeX);
3. a peça de destino continua identificável: **≥ 80 %** da sua área de tinta original
   sobrevive (hoje o peão de c5 perde a base inteira).

**Q2 — `inside` sem tocar nas peças.** Ou o rótulo desloca-se para um canto livre da casa,
ou a casa com peça não recebe rótulo, ou a opção sai da API. Critério: no espécime da p4,
**zero** peças com entalhe (mesma prova de componentes conectados do Q1) **e** os 16 rótulos
inteiros, nenhum cortado por aresta de fileira.

**Q3 — Paridade real entre exportadores.** `compare_exporters.py` tem de comparar
**legendas e cabeça corrente**, não só duas passagens de lances, e comparar **estrutura**
(quais corridas saem em negrito), não só strings. Critério: **zero** divergências nas
legendas e na cabeça corrente; a reticência fica como a única divergência declarada, e o
espaço depois dela é 0,00 pt nos dois. O LaTeX compõe linhas de lances em negrito como o
SVG (hoje 7 spans contra 71).

**Q4 — A justificação vertical precisa de teto e de blocos indivisíveis.**

1. Nenhum vão interno acima de **2 entrelinhas** (20,8 pt) numa página de livro, nem acima
   de **4** numa folha de espécimes. Hoje: 35,6 mm = 8,2 entrelinhas.
2. Um título e o seu primeiro parágrafo formam bloco **indivisível** — nem vão distribuído
   entre eles, nem quebra de página. Hoje a p8 mete 27,8 mm entre os dois.
3. Cabeça de partida + régua + linha de local formam bloco indivisível com vão fixo.
   Critério: ≤ **1 entrelinha** entre a régua e o local (referência C: 4,0 mm; nós: 9,7 mm).
4. Um bloco recuado leva as suas continuações no mesmo recuo. Teste: para todo bloco cujo
   recuo da primeira linha é *d* > 0, toda linha seguinte do mesmo bloco tem recuo ≥ *d*.
5. Nenhuma linha justificada acima de **2,0×** o espaço nominal da página; a linha rebate
   antes disso. Hoje: 3,00×.
6. Uma fileira de espécimes que não cabe **não parte** a série que a seção existe para
   comparar: os quatro tamanhos, na mesma página.

**Q5 — Uma vantagem, medida, contra as cinco referências.** Empate não aprova (§5.1).
Escolham uma e ganhem-na com número:

* **grade de linha de base a 100 % de ocupação e 100 % de registo entre colunas** — hoje
  45 % e 41 %, contra os 100 %/100 % da amostra F; ou
* **símbolos de avaliação como glifos únicos de fonte de xadrez** (`± ∓ ⩲ ⩱ +− −+`), o que
  nenhuma referência do conjunto faz com todos (C faz com três); ou
* **o mesmo livro nos dois exportadores, indistinguível token a token e span a span**, o que
  nenhuma editora do conjunto pode oferecer porque nenhuma tem dois caminhos.

Resolvidos Q1–Q5, e com um conjunto cego novo construído sobre uma página-fonte **inédita**
(P7 §18 do ciclo 1, mais a §3.15 acima), aprovo. Não peço mais do que isto e não aceito
menos.

---

```
VEREDITO: REPROVADO
CICLO: 3
FRENTE: F7 (Tipografia)
```

**A razão, numa linha:** a amostra saiu das duas últimas posições (4º de 6 — condição
cumprida), mas as outras duas condições do ciclo 1 falharam — apontei nela sete defeitos que
não apontei em C, D nem F, e a vantagem clara e mensurável não existe (o pé de coluna
empatou com duas referências; a grade de linha de base perdeu para uma digitalização da
Gambit); somam-se três bloqueantes reabertos por medição própria: o recorte das marcas
desmembra as peças nos dois exportadores, o `inside` passou a corromper as peças em vez das
coordenadas, e os exportadores divergem em cinco pontos e não em um.

**Está perto.** Catorze dos vinte e um pontos verificados vieram limpos, quatro com
ressalva, e a folha é reprodutível. O ciclo 4 é cirurgia, não reconstrução.
