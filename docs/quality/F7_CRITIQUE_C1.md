# F7 — Crítica adversarial, ciclo 1

```
VEREDITO: REPROVADO
CICLO: 1
FRENTE: F7 (Tipografia)
```

---

## Nota de procedimento (honestidade de medição)

Ao listar `benchmarks\reports\blind\` o shell devolveu os tamanhos dos arquivos. Os sete
se agrupam em dois blocos (≈319–325 kB e ≈517–629 kB). **Não usei esse agrupamento como
evidência.** A Fase 1 abaixo foi feita sobre pixels, e está registrada por escrito antes
de o gabarito ser aberto. (Declaração devida: o agrupamento por tamanho **coincidia** com
a divisão nossa/referência. A identificação visual não dependeu dele — ver §"A prova que
fecha a questão", que é um diff pixel a pixel.)

Todas as medidas são minhas, por scripts em `benchmarks\reports\critique\`
(`crop.py`, `squares.py`, `boards2.py`, `inkbox.py`, `baseline.py`, `wordgaps.py`).
Nenhum número do construtor foi aceito sem reprodução. Amostras cegas a 200 DPI:
**1 px = 0,127 mm**, **1 pt = 2,78 px**. As páginas em `proofsheet_png/` estão a **170
DPI**, não a 200 como o relatório afirma. Larguras de traço e corpos de tipo vieram do
vetor do PDF (`get_drawings()['width']`, `get_text('dict')` spans), não do raster.

---

## Comparação às cegas

**Preenchida ANTES de abrir `GABARITO.json`.**

| Amostra | Posição | Justificativa |
|---|---|---|
| **E** | **1º** | Colunas fecham no pé com **0,0 mm** de diferença (última linha entintada em y=1634 nas duas). Hachura fina e uniforme: passo ≈6,5 px, cobertura 26,8 % — lê como um tom, não como uma grade. Serifada humanista com ligaduras reais (`Th`). Diagramas sem coordenadas, escolha deliberada e consistente. Senão: algumas linhas justificadas apertadas. |
| **B** | **2º** | Pé das colunas a 4,6 mm. Hachura de passo 7 px / cobertura 34,5 %. **Dois tamanhos de diagrama na mesma página** (410 px ≈ 52 mm e 340 px ≈ 43 mm) — variação intencional de hierarquia, sinal de composição de verdade. Coordenadas de 22 px a 18 px do quadro. Figurino em texto corrido na linha de base e com o mesmo peso do texto ao redor. |
| **G** | **3º** | Mesmo padrão de B. Perde no fecho de coluna (10,7 mm) e em linhas frouxas: a pior tem razão de espaço entre palavras de 3,75× e há 4 acima de 2,5× na coluna direita. |
| **C** | **4º** | Livro real, o mais fraco das referências. **Justificação apertada até o erro** — em várias linhas as palavras quase encostam ("Blackcanplaysomething", "gives Blacka very bad endgame"). O compositor comprimiu em vez de rebater a linha. Diagramas menores (360 px ≈ 45,7 mm), sem coordenadas. Fecho de coluna bom (1,8 mm). |
| **A** | **5º** | Texto correto (aspas `’`, reticências `…`, meia-risca em `1–0`, figurino **na linha de base**, escala de peça e corpo de coordenada dentro da faixa de referência). Mas: **hachura 1,6× grossa demais** (passo 11 px contra 6–7 px em *todas* as referências; cobertura 19,8 %, a mais baixa das sete); **um parágrafo sem entrada** (y1267, recuo 0 onde o padrão da página é 27 px, sem espaço compensatório); **escada de hifenização partindo um nome próprio** ("iso-" / "Bolo-" em linhas consecutivas, quebrando *Bologan*); pé das colunas a 14,5 mm; e a página **para em y=1479** com conteúdo ainda por compor. |
| **D** | **6º** | Tudo de A (menos a hachura; o cinza chapado de 25 % é mais limpo), **mais dois defeitos que reprovam sozinhos**: (a) o terceiro diagrama começa em y=1424 com 410 px de altura numa página de 1800 px — termina em y=1834, **cortado pela borda**, sem régua de coordenadas e com a fileira 1 fatiada; (b) a cabeça de lance **`14.♘b3!` aparece duas vezes na mesma página**. |
| **F** | **7º** | Idêntica a D em defeitos, e é o tema escuro, onde medi **peça branca sobre casa clara a 2,18:1** — abaixo dos 3:1 da WCAG 1.4.11 para objeto gráfico. O texto do tema escuro está bom (13,49:1), o que evita o desastre, mas não a última posição. |

### Palpite real × gerado (antes da revelação)

| Amostra | Palpite | Evidência |
|---|---|---|
| A | **gerada** | Arestas vetoriais sem ruído de impressão; hachura de regularidade mecânica (passo constante de 11 px, mesmos tocos em todo recorte); régua dupla exata (2,80 px sobre 1,40 px, nivelada); corpo em Times/Nimbus Roman, face padrão de pilha TeX, não face de livro. |
| B | **real** | Ruído de digitalização e espalhamento de tinta; ligadura `Th` de face old-style (Caslon/Jenson); tabuleiro 407×402 px — um renderizador vetorial não produz tabuleiro fora de esquadro; dois tamanhos de diagrama na página. |
| C | **real** | Cabeça corrente com título de obra publicada; artefatos de scan; linhas comprimidas como só compositor humano com pressa produz; ordinal `8th` com `th` sobrescrito. |
| D | **gerada** | Idêntica a A fora dos diagramas; nenhuma editora despacha página com diagrama serrado pela guilhotina. |
| E | **real** | Mesmo formato (1160×1696), face e convenção de C — mesmo livro; ruído de scan; tabuleiro 404×406 px. |
| F | **gerada** | Página de fundo preto não é página de livro impresso; repete o corte de D. |
| G | **real** | Mesmo formato, face e cabeça corrente de B — mesmo livro; ruído de scan; tabuleiro 407×403 px. |

### A prova que fecha a questão (obtida antes da revelação)

Diferenciei **A, D e F pixel a pixel**. São **idênticas** em toda a página exceto:

| Faixa de linhas | O que muda |
|---|---|
| y 69–87 | o fólio: **44**, **45**, **46** |
| y 451–1042 | os dois diagramas (hachura / cinza / tema escuro) |
| y 1384–1402 | a cabeça `14.♘b3!`, **presente só em D e F** |
| y 1424–1799 | o terceiro diagrama, **presente só em D e F**, cortado pela borda |

Duas páginas de dois livros diferentes não podem ser idênticas ao pixel. São três
renderizações da mesma página-fonte, numeradas 44/45/46. E as três **não produzem o mesmo
conteúdo**: o tema hachurado **perde silenciosamente** uma cabeça de lance e um diagrama;
os temas cinza e escuro os **derramam para fora da página**.

### Identidade revelada

`GABARITO.json`: **A = nossa (proofsheet p8), D = nossa (p9), F = nossa (p10)**;
B, G = Quality Chess pp. 165 e 151; C, E = Aagaard pp. 151 e 60.

- **Acertei 7 de 7.** Identifiquei as três nossas e agrupei corretamente os dois livros de
  referência antes de abrir o gabarito.
- **As nossas ficaram em 5º, 6º e 7º — as três últimas posições, incluindo o último
  lugar.**
- **Nenhum palpite de qualidade meu estava errado.** Em nenhum momento chamei uma das
  nossas de "claramente um livro de verdade". O contrário: os defeitos que me fizeram
  identificá-las — hachura grossa, parágrafo sem entrada, diagrama cortado, cabeça
  duplicada — são todos defeitos que **não apontei em nenhuma das quatro referências**.

Carta §2.1: *"a nossa amostra não pode ficar em último lugar, e você não pode ter apontado
nela nenhum defeito que não tenha apontado também nas outras. Se você conseguiu
identificar a nossa por ser pior, é reprovação automática."* As três condições falharam
simultaneamente. **REPROVADO por §2.1, antes mesmo das Fases 2 e 3.**

Observação sobre o arnês: pôr **três variantes de tema da mesma página** num conjunto cego
de sete torna o teste trivialmente derrotável — três amostras com o mesmo texto se
denunciam mutuamente, independentemente da qualidade. O próximo ciclo precisa de **uma**
página nossa por conjunto, e de páginas-fonte diferentes entre si.

---

## Auditoria das alegações do relatório (Fase 2)

Reproduzi tudo. O que se sustenta e o que não se sustenta:

| Alegação (`F7_REPORT.md`) | Resultado da minha reprodução |
|---|---|
| "197 passam, 1 pula" | **Confirmado**, idêntico: `197 passed, 1 skipped in 25.85s`. |
| "LaTeX compilou de verdade" | **Confirmado.** `livro.pdf` tem `producer='MiKTeX pdfTeX-1.40.28'`, 8 fontes Type1 subconjuntadas, 20 desenhos vetoriais. **Recompilei sozinho** de `livro.tex` num diretório limpo: exit 0 nas duas passadas, saída de **160 507 bytes idênticos**, **0 caixas over/underfull**. O sha256 difere só pelo carimbo de tempo do pdfTeX. |
| "18 famílias VERIFIED contra arquivos reais" | **Confirmado por amostragem de 7** (`ChessMerida`, `Chess Leipzig`, `Chess Cases`, `Chess Marroquin`, `ChessAlpha`, `Chess Harlequin`, `Arial-Unicode-MS`): todas existem em `%LOCALAPPDATA%\Microsoft\Windows\Fonts` com o **prefixo sha256 exato** da tabela. `--verify` devolve 18 verificadas / 6 não, com as razões declaradas. A tabela não é fabricada. |
| "Figurino flutuava acima da linha de base; sinal invertido, corrigido" | **Confirmado.** Em `amostra_A`, em `24.♗xh7†`, o pé do bispo tem tinta até y=247; os dígitos `2`,`4` e as letras `x`,`h` terminam exatamente em y=247. Está na linha. |
| "Altura do algarismo ÷ casa = 0,412 (ref. 0,408)" | **Reproduz.** Coordenada de 11,34 pt sobre casa de 18,45 pt; altura de caixa alta Times ≈ 0,662 em → 0,407. Medido no raster: nossa 23 px, referência 22 px. |
| "Largura da moldura = 52,1 mm" | **Reproduz.** 410 px a 200 DPI = 52,07 mm. |
| "Tema escuro: 3,09:1 entre peça preta e casa escura" | **Reproduz** (medi 3,05:1 com a cor amostrada). Passa por 0,05. |
| §7.2 nº 5: "O figurino é mais leve que o negrito. **A referência tem a mesma característica, então não é pior**" | **FALSO, e é pior.** Ver defeito bloqueante nº 8: densidade do figurino ÷ densidade do glifo vizinho — **referência 0,94; nossa 0,56 em romano e 0,43 em negrito**. |
| §7.1 nº 3: "A seta do LaTeX não tem ponta" | **Diagnóstico errado.** A 500 DPI a ponta **Stealth existe e está desenhada** em g7. O defeito real é outro: a ponta fica **soterrada sob o peão preto de g7** e a haste **atravessa o bispo de g5 sem recorte**. Consertar "a ponta que falta" não conserta nada. |
| §1: amostras cegas em `sample_A.png`/`key.json` a 300 DPI | **Não bate com o artefato**: são `amostra_A..G.png` e `GABARITO.json` a **200 DPI**. `proofsheet_png/` está a **170 DPI**, não 200. |
| §2.1: "cada uma das 18 … inspecionada visualmente peça a peça na página 5" | **Não sustentado pelo artefato.** A página 5 mostra **13 famílias inteiras e corta a 14ª pela borda**. `alfonso`, `magnetic`, `adventurer`, `line` e `regular` **não aparecem**. |

---

## Defeitos bloqueantes

### 1. O compositor SVG não tem limite inferior de página. Conteúdo é cortado ou perdido em 5 das 10 páginas.

**Onde:** `benchmarks/reports/proofsheet.pdf`, páginas 1, 3, 5, 9 e 10; `blind/amostra_D.png`,
`amostra_F.png`. Origem: `tools/typeset_page.py` / `tools/typeset_proofsheet.py`.

**O que:** medi, para cada página, a coordenada `y` do conteúdo mais baixo contra a altura
do aparo (648 pt) e contei tinta no último milímetro do papel:

| Página | Conteúdo mais baixo | Além do aparo | Tinta no último mm |
|---|---|---|---|
| 1 | 657,6 pt | **+9,6 pt** | 1119 px |
| **3** | **846,1 pt** | **+198,1 pt = 70 mm** | 888 px |
| 5 | 655,6 pt | +7,6 pt | 170 px |
| 9 | 679,7 pt | +31,7 pt = 11 mm | 465 px |
| 10 | 679,7 pt | +31,7 pt = 11 mm | 2486 px |

A margem inferior declarada é 16 mm (45 pt), então a última linha legal está em y≈603 pt.
A página 3 passa **70 mm** disso: aproximadamente um terço do conteúdo da página não está
no papel. Na página 9/10 o terceiro diagrama começa em y=1424 px, tem 410 px, e termina em
y=1834 numa folha de 1800 — a fileira 1 sai serrada ao meio e a régua de coordenadas
inteira desaparece.

**Como reproduzir:** `.venv\Scripts\python.exe tools\typeset_proofsheet.py --png`, depois
abrir `page_03.png` e `page_09.png` e olhar a borda inferior; ou rodar o teste que escrevi
(o laço `get_drawings()`/`get_text('dict')` comparando `rect.y1` com `page.rect.height`).

**Por que reprova:** carta §3.3, primeiro item da lista visual — "Qualquer texto cortado".
E o pior é o comportamento **não determinístico entre temas**: a mesma página-fonte, no
tema hachurado, **descarta** silenciosamente a cabeça `14.♘b3!` e o diagrama (a coluna
esquerda simplesmente para em y=1365 com 27 mm de coluna livre); nos temas cinza e escuro
os **derrama** para fora do papel. Duas falhas diferentes para a mesma condição, escolhidas
pela cor das casas. Isso é "falha silenciosa" (§3.3, Reconhecimento) num compositor de
página.

O relatório chama isso de "as colunas não se alinham no pé" (§7.1 nº 2). Não é. Não há pé.

### 2. Cabeça de lance duplicada na mesma página

**Onde:** `proofsheet.pdf` páginas 9 e 10 (`amostra_D`, `amostra_F`), y≈1384 e y≈1396.

**O que:** `14.♘b3!` é composta **duas vezes**: uma no pé da coluna esquerda (seguida do
diagrama cortado) e outra na coluna direita (seguida de "Black cannot maintain his hanging
pawns in the ideal c5-d5 position."). Recorte em
`benchmarks/reports/critique/D_dup_row.png`.

**Por que reprova:** o leitor vê a mesma jogada anunciada duas vezes com corpos diferentes.
Em livro isso é errata.

### 3. `CoordinatePlacement.inside` produz coordenadas ilegíveis e destrói as peças

**Onde:** `proofsheet.pdf` p3, seção 3, terceiro tabuleiro (rótulo `inside`). Ampliação em
`benchmarks/reports/critique/proof_inside_coords.png` (900 DPI).

**O que:** as coordenadas são desenhadas **por baixo** das peças, sem recorte nem inversão:

- os algarismos **8 e 7 desapareceram** — estão sob a torre de a8 e o peão de a7;
- o algarismo **2 está desenhado dentro do peão branco de a2**, corrompendo o contorno da
  peça a ponto de ela poder ser confundida com outra figura;
- as letras **c, d, f e g estão escondidas** atrás da torre de c1, da dama de d1, da torre
  de f1 e do rei de g1 — só a, b, e, h são legíveis;
- o **"1" e o "a" se sobrepõem** no canto inferior esquerdo e leem como um único token
  "1a".

**Como reproduzir:** renderizar a p3 do proofsheet com clip em (700,980)–(1010,1290) px a
170 DPI, a 900 DPI.

**Por que reprova:** primeiro item da lista visual da carta — texto sobreposto. É uma opção
**oferecida na API** que produz um diagrama inutilizável. Não está no relatório.

### 4. Marcas desenhadas sobre as peças sem recorte, nos dois exportadores

**Onde:** `proofsheet.pdf` p4 (os quatro tabuleiros); `latex/livro.pdf` p1, diagrama
inferior direito. Ampliação: `benchmarks/reports/critique/latex_arrow_500.png`.

**O que:**

- **Haste sobre peça:** a seta d1→d7 (p4, tabuleiro 1) corta o peão preto de d5 ao meio com
  uma barra cinza-escura. No LaTeX a haste g3→g7 atravessa o bispo branco de g5. Em ambos a
  haste não tem contorno nem knockout, então onde cruza uma peça preta as duas se fundem.
- **Ponta soterrada:** a ponta da seta d1→d7 fica sob o cavalo de d7; a c1→c5 sob o peão de
  c5; a do LaTeX sob o peão preto de g7 — só as farpas aparecem por baixo.
- **Cauda dentro da peça de origem:** a seta g2→b7 começa dentro do bispo de g2.
- **Setas de salto de cavalo (p4, tabuleiro 2):** os trechos horizontais das três setas
  correm por cima dos peões de b2, c2, e2 e f2, cortando **quatro peças** com a mesma barra.
- **Círculos quebrados:** os círculos em b7 e g2 (p4, tabuleiro 3) são interrompidos pela
  base flarada do bispo, que é desenhada por cima; o círculo em d5 (tabuleiro 4) é
  cinza-escuro sobre um peão preto — a metade inferior é invisível.

**Por que reprova:** uma anotação que destrói a informação que anota é pior que anotação
nenhuma. O relatório admite só "a seta do LaTeX não tem ponta", que além de ser um
subconjunto é um **diagnóstico errado** (a ponta existe; ver a tabela da Fase 2).

### 5. O destaque de casa apaga a distinção claro/escuro

**Onde:** `proofsheet.pdf` p4, tabuleiro 3 (`destaques + circulos`); LaTeX `backfields`.

**O que:** medido no raster da p4:

| Casa | Cinza |
|---|---|
| casa clara comum (a4, e4) | 255 |
| casa escura comum (b4, d4) | 191 |
| **c5 destacada (naturalmente escura)** | **135** |
| **d5 destacada (naturalmente clara)** | **135** |

O destaque **substitui** a cor da casa por um chapado único em vez de matizar as duas.
Consequências medidas:

- c5 e d5 ficam **indistinguíveis** — o xadrez do tabuleiro morre dentro do destaque, e o
  leitor perde a referência de cor de casa exatamente na região que o autor quis destacar;
- destaque contra casa escura comum: **1,95:1** — mal se enxerga onde o destaque começa;
- peça preta sobre destaque cai de **11,42:1 para 5,85:1**.

**Como reproduzir:** amostrar o canto (a 0,38 da casa, fora do glifo) de c5, d5, b4 e a4 no
tabuleiro 3 da p4.

**Por que reprova:** contraste e semântica perdidos por construção. A correção é matizar
ambas as cores pelo mesmo delta, não sobrescrevê-las.

### 6. O peso da moldura não é um valor de sistema: varia 2,3× dentro do mesmo documento

**Onde:** todo o `proofsheet.pdf`. Extraído do vetor (`get_drawings()['width']`), não do
raster.

| Página | Largura do tabuleiro | Traço | Razão |
|---|---|---|---|
| 1, 2 (famílias) | 118,5 pt | 0,516 pt | 1/230 |
| 3 `hairline` | 103,2 pt | 0,510 pt | 1/202 |
| 3 `rule` | 106,2 pt | 0,986 pt | **1/108** |
| 3 `double` | 106,7 pt | 1,091 pt | **1/98** |
| 4 (marcas) | 157,4 pt | 0,686 pt | 1/230 |
| 6, 7 — 20 mm | 51,1 pt | 0,510 pt | **1/100** |
| 6, 7 — 40 mm | 101,6 pt | 0,510 pt | 1/199 |
| 6, 7 — 60 mm | 152,4 pt | 0,663 pt | 1/230 |
| 6, 7 — 90 mm | 228,6 pt | 0,995 pt | 1/230 |
| **8, 9, 10 (página de livro)** | 147,7 pt | 1,372 pt | **1/108** |

Medi as referências para saber qual é o valor certo:

| Referência | Razão |
|---|---|
| Quality Chess p165 | 1/122 |
| Quality Chess p151 | 1/129 |
| Aagaard p60 | 1/139 |
| Aagaard p151 | 1/94 |

**O que isto diz:**

1. As referências mantêm a moldura entre **1/94 e 1/139** em todos os tamanhos. A nossa
   varia de **1/98 a 1/230** — um espalhamento de 2,3× no mesmo PDF.
2. Os diagramas de 40, 60 e 90 mm do proofsheet têm moldura de **1/199 a 1/230**, ou seja
   **cerca de metade** do peso de referência: leem anêmicos.
3. O traço é **travado em 0,51 pt** abaixo de ~117 pt de tabuleiro, então a moldura de
   20 mm é **1/100** — 2,3× mais pesada em termos relativos que a de 60/90 mm. É
   literalmente o exemplo de defeito que a carta cita.
4. Dois tabuleiros de tamanho praticamente igual no mesmo documento — 152,4 pt (p6) e
   147,7 pt (p8) — têm molduras de **0,663 pt e 1,372 pt**. Diferença de 2,1× entre
   componentes equivalentes (carta §3.3: "Espaçamento inconsistente entre elementos
   equivalentes").

**Crédito onde é devido:** a moldura da *página de livro* (1/105–1/107) está dentro da
faixa de referência. O problema é que esse valor não é o valor do sistema.

**Como reproduzir:** o laço sobre `get_drawings()` filtrando retângulos traçados
aproximadamente quadrados com largura > 40 pt.

### 7. A hachura do SVG é 1,6× mais grossa que toda referência — e mais grossa que a do nosso próprio LaTeX

**Onde:** `board_svg.py`, tema `hatched`. Medido numa casa escura vazia, varredura
horizontal pelo meio da casa, a 200 DPI.

| Renderizador | Traço | Vão | Passo | Linhas por casa | Cobertura de tinta |
|---|---|---|---|---|---|
| **Nosso SVG** | 2 px | **9 px** | **11 px** | **4** | **19,9 %** |
| **Nosso LaTeX** (pacote `chessboard`) | 1–2 px | 5–6 px | 7 px | 6 | 21,9 % |
| Quality Chess p165 | 2 px | 5 px | 7 px | 7 | 34,5 % |
| Quality Chess p151 | 2–3 px | 4–5 px | 7 px | 6–7 | 34,2 % |
| Aagaard p60 | 2 px | 4–6 px | 6,5 px | 7 | 26,8 % |
| Aagaard p151 | 1 px | 5 px | 6 px | 7 | 22,1 % |

Com 4 linhas grossas por casa em vez de 6–7 finas, cada linha vira um elemento gráfico
isolado que **compete com o contorno da peça** em vez de se fundir num tom. É o que se vê
ao ampliar `critique/A_hatch_zoom.png` ao lado de `B_hatch_zoom.png`. E a cobertura de
19,9 % é a **mais baixa das sete amostras**: as casas "escuras" da nossa página são as mais
claras da mesa.

Constrangedor: o nosso caminho LaTeX, que ninguém ajustou, está mais perto da referência
que o nosso caminho SVG, que foi ajustado. §3.3 nº 5 do relatório conta que a cobertura foi
**fixada em 19 %** para resolver o preto sólido a 20 mm — o alvo escolhido está errado; a
referência fica em 27–35 %.

### 8. O figurino tem metade da cor do tipo ao lado — e a alegação de paridade com a referência é falsa

**Onde:** todo o caminho SVG. Medido como densidade de tinta contínua (`1 − v/255`) dentro
da caixa do glifo, nas amostras cegas a 200 DPI.

| Contexto | Figurino | Glifos vizinhos | Razão |
|---|---|---|---|
| **Referência B, texto romano** (`…♖g8-g4.`) | 44,5 % | 46,4 % / 48,5 % | **0,94** |
| **Nossa, texto romano** (`…♗xg6.`) | 19,3 % | 31,4 % / 37,6 % | **0,56** |
| **Nossa, cabeça em negrito** (`24.♗xh7†`) | 20,3 % | 46,1 % / 49,0 % | **0,43** |

Duas conclusões:

1. **A referência não tem "a mesma característica".** O figurino dela carrega praticamente
   a mesma cor do tipo ao redor (0,94). O nosso carrega pouco mais da metade.
2. **O nosso figurino não responde ao negrito.** Sua densidade é 20,3 % em contexto negrito
   e 19,3 % em romano — é o mesmo glifo no mesmo peso. Numa cabeça de lance em negrito ele
   "desmaia": razão 0,43, ou seja **57 % mais claro que as letras que o cercam**.

Ampliações: `critique/A_fig1.png` (nossa, negrito) contra `critique/B_boldline.png`
(referência, romano).

**Por que reprova:** carta §3.3 — "Ícones de origens diferentes misturados (peso, estilo,
grade)". E a alegação de §7.2 nº 5 do relatório sustenta uma decisão de não-consertar sobre
uma premissa que a medição derruba.

### 9. O exportador LaTeX ignora inteiramente `typography.py`

**Onde:** `benchmarks/reports/latex/livro.pdf`, camada de texto extraída; fonte em
`livro.tex` linha 57 e 66.

O `.tex` escreve SAN cru dentro de `\mainline{...}` e recebe o estilo padrão do xskak.
Comparando **a mesma passagem** nos dois exportadores:

| Elemento | Caminho SVG (p8) | Caminho LaTeX (p1) |
|---|---|---|
| Número de lance | `1.d4` | `1 d4` (sem ponto) |
| Captura | `cxd5` (x minúsculo) | `c×d5` (sinal de multiplicação) |
| Roque | `0–0` (zero + meia-risca) | `O-O` (letra O + hífen) |
| Xeque | `♗xd2†` (adaga) | `…Xd2+` (mais) |
| Reticências | `13…bxc5` (U+2026) | `13. . . bXc5` (três pontos espaçados) |
| Legenda vs linha principal | — | **discordam entre si na mesma página**: legenda "After 13.dxc5" com `x` minúsculo, linha principal `13 d×c5` |

O relatório dedica §3.3 nº 2 a implementar `castling_dash` como opção de casa porque
"Quality Chess usa meia-risca" — e o exportador LaTeX emite `O-O`. Todo o trabalho de
`typography.py` termina no SVG.

**Por que reprova:** F8 exporta os dois formatos. Um livro exportado nos dois sai com
**duas notações diferentes**. O relatório admite apenas "conjunto de peças diferente"
(§4.2), que é a menor das divergências. Some-se: a fonte da tabuleiro no LaTeX é
`Chess-Alpha` e a do figurino em texto é `SkakNew-Figurine-Bold` — **dois desenhos de peça
dentro do mesmo documento LaTeX**, o que o relatório também não menciona.

### 10. A página LaTeX tem um buraco de 25 mm e um título de exibição quebrando dentro de uma coluna de 63 mm

**Onde:** `livro.tex` linha 53: `\chapter*{...}` **dentro** de `\begin{multicols}{2}`.
Render: `critique/latex_p1_200.png`.

`\chapter*` injeta o espaço vertical de abertura de capítulo dentro da coluna, produzindo
**~25 mm de branco morto** no topo da coluna 1, e compõe o título em corpo de exibição
(≈24 pt) numa medida de 63 mm, onde ele quebra em duas linhas no meio da frase:
"Family One –" / "d4 and . . . d5". O mesmo string é uma cabeça corrente de 9 pt no caminho
SVG. E o `\ldots` em corpo de exibição sai como três pontos largamente espaçados.

### 11. Coordenadas de 3,92 pt no diagrama de 20 mm, sem piso nem supressão

**Onde:** `proofsheet.pdf` p6/p7, primeiro tabuleiro. Corpos extraídos do vetor:

| Diagrama | Largura | Corpo da coordenada |
|---|---|---|
| 20 mm | 51,1 pt | **3,92 pt** |
| 40 mm | 101,6 pt | 7,84 pt |
| 60 mm | 152,4 pt | 11,76 pt |
| 90 mm | 228,6 pt | 17,63 pt |

A escala é rigorosamente proporcional (0,077 do tabuleiro em todos), o que está certo como
regra — mas **não há piso**. 3,92 pt de Times New Roman não sobrevive a nenhuma impressão
offset: as hastes finas somem. Qualquer livro que usa diagrama miúdo em linha **omite as
coordenadas**; nós as imprimimos ilegíveis. Não há aviso e não há supressão automática.

No mesmo diagrama o contorno da peça sai em ≈0,2 pt (casa de 2,26 mm), abaixo da tolerância
de prova: as peças **brancas sobre casa clara** vão desaparecer na impressão.

**Agravante:** a legenda dessa página, escrita pelo próprio construtor, é *"O peso do traco
e o corpo das coordenadas tem de sobreviver aos quatro"*. Ele construiu o teste, publicou-o
na folha de prova, e não reportou que ele falha.

### 12. Entrada de parágrafo ausente, sem espaço compensatório

**Onde:** `amostra_A`/`D`/`F`, coluna direita, y1267 (`proofsheet.pdf` p8–10).

Medi o recuo da primeira linha de cada parágrafo da coluna: o padrão é **27 px** (≈3,4 mm,
≈1 em). A linha "Better was: 13…♘xc5 …" começa em recuo **0**. A linha anterior
("problem.") termina 416 px antes da margem, então é fim de parágrafo — e o passo de linha
entre elas é 28 px, idêntico às demais (29–30 px). Ou seja: **nem entrada, nem espaço**.
O leitor não consegue ver onde o parágrafo começa.

Carta §3.3, Tipografia: "Espaçamento de parágrafo que muda sem razão semântica".

---

## Defeitos não bloqueantes

1. **Hifenização parte nome próprio.** `amostra_A` coluna direita: "…an iso-" / "lani
   position; compare the game Vitiugov – Bolo-" / "gan from…". Duas hifenizações em linhas
   consecutivas (escada de 2) e a segunda quebra *Bologan*. Pior: a correção §3.3 nº 7 do
   relatório (colar a meia-risca à palavra anterior) **criou** essa quebra — antes o
   travessão caía sozinho na linha, agora o nome é partido. Falta uma regra de "não
   hifenizar nome próprio" e de manter o par de jogadores indivisível.
2. **Pé das colunas a 14,5 mm** na página de livro (admitido em §7.1 nº 2). Referências:
   0,0 / 1,8 / 4,6 / 10,7 mm.
3. **Indicador de lance flutuando fora da moldura.** Quadrado preto sólido (SVG p3 e todos
   os diagramas do LaTeX) ou triângulo (SVG p3), destacados do quadro por ~1 mm de branco,
   acima da aresta superior. Lê como borrão de tinta. Os dois desenhos também não têm o
   mesmo peso óptico.
4. **`FrameStyle.shadowed`** desenha uma sombra chapada 100 % preta deslocada. Não é
   convenção de livro, e desloca o centro óptico do diagrama, de modo que um diagrama
   `shadowed` não alinha com um `hairline` na mesma coluna.
5. **A calha da coordenada não compensa o peso da moldura** (p3): as letras são posicionadas
   a partir da aresta do tabuleiro, não da aresta externa do quadro, então molduras pesadas
   as empurram visualmente para perto. Elementos equivalentes, espaçamentos diferentes.
6. **Zero caracteres acentuados nas 10 páginas da folha de prova.** "posicao", "regua",
   "pe", "peca", "traco", "circulos", "familias". Verifiquei que **não é limitação do
   renderizador** — `_can_render('é')`, `'ç'`, `'ã'`, `'É'` retornam todos `True`. É o
   fonte de `tools/typeset_proofsheet.py` que foi digitado em ASCII. Numa frente de
   tipografia, o entregável que demonstra qualidade tipográfica está sem acentos.
7. **Aspas retas convivendo com curvas no mesmo documento**: 4× U+0027 e 7× U+2019. Causa
   localizada: `heading()` (linha 62 de `typeset_proofsheet.py`) chama `canvas.text()`
   direto, **contornando `tp.prepared()`**. Por isso `7. Tamanhos - tema 'book'` mantém
   aspa reta e hífen onde cabe meia-risca. Cabeçalhos e legendas nunca recebem a passada
   tipográfica.
8. **`tp.prepared(..., "en")` está fixo em inglês** em todas as chamadas, inclusive nas
   legendas em português — o hifenizador multilíngue existe e o entregável usa padrões
   ingleses para texto português.
9. **`\diagramnumber` está definido e nunca é usado** (`livro.tex` linhas 47–49). O
   artefato LaTeX não tem número de diagrama nenhum; as legendas são "After 13.dxc5.". A
   afirmação de §7.2 nº 10 ("O LaTeX tem `\diagramnumber`") é verdadeira sobre a macro e
   falsa sobre a saída.
10. **A moldura sai 10 % menor que o rótulo de tamanho**: os diagramas rotulados 20/40/60/90
    mm medem 18,1 / 35,9 / 53,8 / 80,8 mm de quadro a quadro. A razão é constante (0,898),
    então o "tamanho" inclui a calha de coordenadas — mas quem pedir 90 mm recebe 81.
11. **`--verify` despeja ~48 linhas de aviso de timestamp do fontTools** antes da tabela.
12. **Erros de documentação no relatório** (§1: `sample_A.png`/`key.json` a 300 DPI; na
    verdade `amostra_A..G.png`/`GABARITO.json` a 200 DPI; `proofsheet_png/` está a 170 DPI,
    não 200).
13. **§2.1 do relatório reivindica inspeção visual peça a peça das 18 famílias na p5**; a
    página mostra 13 e corta a 14ª. Cinco famílias verificadas nunca foram olhadas.
14. **O conjunto cego contém três variantes de tema da mesma página-fonte**, o que derrota
    o procedimento.
15. Tema escuro: **peça branca sobre casa clara a 2,18:1**, abaixo do mínimo de 3:1 da WCAG
    1.4.11 para objeto gráfico. (O par que o relatório reporta, peça preta sobre casa
    escura, mede 3,05:1 e passa; o par que ele não reporta é o que falha.)

---

## O que verifiquei e está sólido

Registro por dever de §5.5 — reprovar tudo é tão inútil quanto aprovar tudo.

- **A suíte roda e o número bate**: 197 passam, 1 pula, em 25,85 s.
- **O LaTeX compila de verdade.** Recompilei sozinho num diretório limpo: exit 0 duas
  vezes, 160 507 bytes, **0 caixas over/underfull**. `\widowpenalty`/`\clubpenalty`/
  `\brokenpenalty` em 10000 — viúvas e órfãs tratadas no caminho LaTeX.
- **A tabela de fontes não é fabricada.** 7 de 7 arquivos conferidos batem o prefixo
  sha256 exato. `--verify` reproduz 18/6 com as razões declaradas.
- **A correção da linha de base do figurino é real e está certa.** Tinta do bispo termina
  em y=247, exatamente com os dígitos e letras vizinhos.
- **A escala das peças bate com a referência** (peão 55–57 % × 78–80 % da casa; referências
  57–59 % × 77–81 %). Achei que estivessem grandes demais; medi; estava errado.
- **O corpo das coordenadas bate com a referência** (23 px contra 22 px; razão 0,412 contra
  0,408 — o número do relatório reproduz).
- **A moldura da página de livro (1/105) está dentro da faixa de referência (1/94–1/139).**
- **Aspas tipográficas, reticências, meia-risca e o travessão de roque estão corretos** no
  caminho SVG: `White’s`, `…e6-e5`, `1–0`, `0–0`.
- **A régua dupla da cabeça de partida é uma régua escocesa legítima** (1,008 pt sobre
  0,504 pt, razão 2:1, nivelada). Achei que fosse um borrão; medi; não é.
- **A justificação não é pior que a referência.** Maior vão entre palavras numa linha de
  prosa: nossa 14 px, referência G 17 px. A reclamação do relatório em §7.2 nº 8 é honesta
  mas o defeito não é visível contra o padrão da concorrência.
- **O tema escuro está competente onde importa mais**: texto a **13,49:1**, paleta
  consistente entre os diagramas da página (medi: casa clara 155,163,171; casa escura
  94,102,110; fundo 27,31,35 — os mesmos valores nos dois tabuleiros), e as cores das peças
  **não** foram invertidas. Não é o claro invertido.
- **O relatório é honesto onde é honesto.** §7 admite 18 defeitos, vários deles reais, e
  §3.3 nº 8 registra um erro do próprio autor. Isso é raro e conta a favor. O problema é
  que os defeitos que ele **não** admitiu são maiores que os que admitiu.

---

## O que especificamente precisa mudar para eu aprovar

Ordenado por bloqueio. Cada item é verificável.

**P1 — Dar um pé à página.**
1. `tools/typeset_page.py` precisa de um limite inferior de mancha obrigatório. Nenhum
   bloco pode ser emitido abaixo dele; um bloco que não cabe vai para a próxima coluna, e
   se não houver, para a próxima página.
2. O compositor deve **falhar alto** (exceção, não aviso) quando um bloco não couber e não
   houver destino — nunca descartar em silêncio, como o tema hachurado faz hoje.
3. Critério de aceite: um teste que percorre toda página gerada e afirma
   `max(y1 de todo desenho e toda linha de texto) ≤ altura − margem_inferior`. Ele tem de
   passar nas 10 páginas do proofsheet. Hoje falha em 5.
4. Corrigir a duplicação de `14.♘b3!` e adicionar um teste que afirme que nenhuma cabeça de
   lance aparece duas vezes na mesma página composta.
5. A mesma fonte, nos três temas, tem de gerar **exatamente o mesmo conteúdo**. Teste:
   compor a página nos três temas e comparar a lista de blocos emitidos.

**P2 — Consertar as marcas e o `inside`.**
6. Toda marca (seta, círculo, destaque) precisa de ordem de pintura definida e de recorte:
   ou desenhar **sob** as peças, ou desenhar sobre elas **com um knockout** de ≈0,3 mm na
   cor da casa em volta do traço. A ponta da seta tem de ficar visível sobre a peça de
   destino nos dois exportadores.
7. `CoordinatePlacement.inside`: recortar as peças ou reverter a coordenada em caixa opaca.
   Critério: no diagrama de p3 os 16 rótulos têm de ser legíveis. Hoje 7 estão destruídos.
8. Destaque de casa: matizar as **duas** cores de casa pelo mesmo delta, preservando o
   xadrez. Critério: numa fileira de casas destacadas, casa clara destacada ≠ casa escura
   destacada, com pelo menos a mesma diferença que 255/191 tem hoje.

**P3 — Fazer da moldura e da hachura valores de sistema.**
9. Uma única regra de peso de moldura, proporcional ao tabuleiro, em **1/110 ± 15 %**
   (faixa medida nas quatro referências), com um piso absoluto só abaixo de ~25 mm — e
   nesse regime, **suprimir as coordenadas** em vez de imprimir 3,92 pt.
10. Passo de hachura em **≈0,85 mm** (6–7 linhas por casa a 52 mm) e cobertura de tinta
    alvo de **28–32 %**, não 19 %. Critério: repetir a minha medição de cobertura na casa
    escura vazia e cair dentro da faixa das referências.
11. Critério de aceite conjunto: extrair `get_drawings()['width']` de todos os diagramas do
    proofsheet e afirmar que `largura_tabuleiro / traço` fica numa faixa de ±15 % em todas
    as páginas. Hoje o espalhamento é de 2,3×.

**P4 — Dar peso ao figurino.**
12. O figurino precisa de uma variante mais pesada para contexto negrito, e o peso base
    precisa subir. Critério objetivo, reproduzível com o meu método: **densidade de tinta do
    figurino ÷ densidade média dos dois glifos vizinhos ≥ 0,85** em texto romano e em
    negrito. Hoje: 0,56 e 0,43. Referência: 0,94.

**P5 — Unificar os dois exportadores.**
13. `typeset_text()` tem de rodar sobre o SAN **antes** de chegar ao `\mainline`, ou o
    gerador LaTeX tem de configurar o xskak para a mesma casa (`\xskakset` para ponto após o
    número, `x` minúsculo, `0–0`, `†`). Critério: extrair o texto dos dois PDFs para a mesma
    passagem e comparar token a token. Hoje divergem em 5 elementos.
14. Um só desenho de peça por documento: tabuleiro e figurino em texto da mesma família.
    Hoje o LaTeX mistura `Chess-Alpha` no tabuleiro com `SkakNew-Figurine-Bold` no texto.
15. Tirar `\chapter*` de dentro de `multicols`; a cabeça de partida tem de ser um cabeçalho
    de coluna, não uma abertura de capítulo.

**P6 — A folha de prova é o entregável; tratá-la como tal.**
16. Passar cabeçalhos e legendas por `tp.prepared()` e escrever o texto em português com
    acentos — o renderizador já suporta (`_can_render('é') is True`). Passar o idioma certo
    ao hifenizador em vez de `"en"` fixo.
17. A p5 tem de mostrar **as 18** famílias verificadas, ou o relatório tem de parar de dizer
    que todas foram inspecionadas ali.

**P7 — Refazer o teste cego direito.**
18. **Uma** página nossa por conjunto, de fonte diferente das demais, misturada com pelo
    menos quatro páginas de referência, incluindo ao menos uma editora fora da Quality Chess
    (a carta §2.2 pede New in Chess, Everyman, Gambit).
19. E, como §7.1 nº 1 do próprio relatório reconhece: a comparação vetor-contra-scan nos
    favorece. Enquanto a referência for digitalização, o resultado da comparação é um piso,
    não um teto.

**Para o ciclo 2 eu aprovo quando:** os doze bloqueantes estiverem fechados com os testes
acima verdes, e um novo conjunto cego construído segundo P7 puser a nossa amostra **fora
das duas últimas posições**, sem que eu consiga apontar nela nenhum defeito que não aponte
também nas referências. Empate não basta (§5.1) — quero pelo menos uma vantagem clara e
mensurável sobre as quatro páginas de referência. A candidata natural é o pé de coluna:
nenhuma das quatro referências acerta melhor que 0,0 mm, e um compositor que balanceie
colunas de verdade e trate viúvas e órfãs no caminho SVG (o `fill_columns` que §7.2 nº 9
admite existir e não ser usado) entrega isso por construção.
