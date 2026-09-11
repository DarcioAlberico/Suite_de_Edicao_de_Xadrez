# F9 — Crítica adversarial, ciclo 1

```
VEREDITO: REPROVADO
CICLO: 1
FRENTE: F9 (Interface)
```

---

## Nota de procedimento

Não há conjunto cego para a F9 nesta máquina — não existem capturas de Affinity Publisher,
DaVinci Resolve, Chessbase ou Scrivener no disco. A carta §2.1 é portanto substituída, por
instrução da coordenação, por um **julgamento explícito e itemizado dos nove critérios**
(§2 abaixo), cada um com a medida que o sustenta.

**Todas as medidas são minhas.** Os instrumentos estão em
`benchmarks\reports\critique\ui\`: `seg.py`, `censo2.py`, `ritmo.py`, `medidas.py`,
`contraste_no_pixel.py` (medida sobre os PNGs) e `sonda.py`, `casos_ruins.py`, `estados.py`,
`titulo_longo.py`, `sobreposicao.py` (medida sobre a janela viva). Nenhum número do construtor foi aceito sem reprodução; onde reproduzi,
digo que reproduzi (§3), e onde o número do construtor está **certo** também digo (§3 e §6).

**Olhei as 54 capturas de `benchmarks\reports\ui\`** — as 24 `depois_*`, as 24 `antes_*`, as
duas pranchas `amostrario_*` e as quatro `v1_*` — e produzi mais 14 capturas próprias
(1024×768 recusado, título longo, prancha de estados) porque a Fase 3 exigia telas que a
captura feliz não tem.

**Uma correção de fato, antes de tudo:** os arquivos chamados `*_1280x800_*` **não têm 800 px
de altura**. Medidos: `depois_claro_*` = 1280×**890**, `depois_escuro_*` = 1280×**924**. O
mesmo vale para o conjunto `antes_*` (888 / 922). A janela recusou o tamanho pedido e o
arnês gravou o que ficou, mas o nome do arquivo e a tabela do §10 do relatório continuam
dizendo "1280×800". Isso importa porque é exatamente o tamanho em que o portão falha.

---

## §2 — Os nove critérios, um a um: isto sobrevive ao lado do Affinity Publisher?

Contexto de escala, medido (`sonda.py controles` / `sonda.py enfases`, janela 1920×1080, `1937 Kemeri.pdf` aberto):

| aba | controles interativos visíveis | `QPushButton` | primários | destrutivos | neutros |
|---|---|---|---|---|---|
| Resultado | 52 | 27 | 3 | 1 | 23 |
| Estudo | 53 | 46 | 3 | 3 | **40** |
| Revisão | 33 | 27 | 3 | 1 | 23 |
| Texto | 41 | 29 | 2 | 1 | 26 |
| Dataset | 40 | 29 | 2 | 3 | 24 |
| Galeria | 54 | 33 | 2 | 2 | 29 |

### 1. Hierarquia visual — **NÃO SOBREVIVE**

**Não.** Em um segundo o olho não encontra a ação principal, porque **há três ações
principais simultâneas** em Resultado, Estudo e Revisão: `OCR melhor diagrama` (barra do
visor), `Anotar página` (rodapé do visor) e a primária da aba (`Salvar a posição` /
`Carregar OCR atual` / `Corrigir agora`). Três botões azuis, em três cantos diferentes da
mesma tela. A regra `estilos.conferir_barra` cobra **uma ênfase por barra**, e a janela tem
três barras — a regra é cumprida e o resultado é o oposto do que ela existe para garantir.

E o que o olho de fato encontra primeiro é pior. Medi o retângulo com maior acento visual da
aba Resultado: é uma caixa de **1059×140 px com anel de foco azul de 2 px permanente**
(`#0b5ed7` na pele clara, `#84b6ff` na escura, confirmado no pixel em `x=11..12` de
`depois_claro_1920x1080_resultado.png`, `depois_escuro_*` e `depois_claro_1280x800_*`).
Sondei o widget (`sonda.py vazio`): é um **`QListWidget` vazio**, `placeholderText` inexistente,
`toolTip()` vazio, `accessibleName() == 'Lista'`, sem título, sem legenda, com
`setMaximumHeight(ALTURA_MAXIMA_DA_LISTA)` reservando 5 linhas mesmo quando há zero itens.
Densidade de tinta medida: **1,54 %**. **O elemento mais destacado da aba mais importante é
uma caixa vazia sem uma palavra dentro.**

### 2. Ritmo espacial — **SOBREVIVE COM RESSALVA**

Aqui o construtor merece crédito e eu o dou. A escala existe e está escrita como dado:
`ui/tipografia.FOLGAS = {MOLDURA: 14, FOLGA: 10, LINHA: 6, MÍNIMA: 2}` — **quatro valores**,
dentro dos "3 a 5" que a coordenação pediu. E o código **obedece**: varri
`src/chess_diagram_ocr/qt/` e não há um único `setSpacing(<literal>)` diferente de zero;
todos são `espaco.linha()`, `espaco.folga()` ou `espaco.minima()`.

Medido no pixel (`ritmo.py` sobre as seis abas claras a 1920):

| grandeza | valores distintos medidos |
|---|---|
| vão horizontal entre controles da mesma fila | **9 (2×) e 10 (35×)** |
| passo vertical entre filas do painel esquerdo | **32 px, constante** (Estudo: 57 → 89 → 121 → 153) |
| vão vertical entre filas da barra do visor | **6, 10, 10** |

Duas ressalvas, e a segunda é real:

- o jitter de 1 px (9 vs 10) é sobra de distribuição do `QHBoxLayout`, não decisão — não conta;
- **o vão entre a fila 1 e a fila 2 da barra do visor é 6 px e entre a 2 e a 3 é 10 px.**
  Quatro filas de botões visualmente idênticas, com um agrupamento sinalizado por **4 px de
  diferença**. Isso está abaixo do limiar em que alguém percebe um grupo. O sistema de espaço
  tem um mecanismo de agrupamento e ele é invisível.

### 3. Alinhamento — **NÃO SOBREVIVE**

Medi o `x` do primeiro controle da primeira fila do painel esquerdo, por aba, nas duas peles:

| aba | x da fila (claro) |
|---|---|
| Estudo | 9, 9, **8**, 9 |
| Revisão | 8 |
| Dataset | 8 |
| Galeria | 9 |
| **Texto** | **13** (e 12 quando a primeira fila tem foco, por causa da borda de 2 px) |
| Resultado | não tem fila superior (ver §5 abaixo) |

**Trocar da aba Estudo para a aba Texto desloca a margem esquerda do conteúdo em 4–5 px.**
A faixa de abas fica parada e o que está debaixo dela pula. E dentro da própria aba Estudo as
filas começam em 8 e em 9. Não há grade: há quatro números onde deveria haver um.

### 4. Densidade × vazio — **NÃO SOBREVIVE. É o pior número do relatório.**

Medi a fração de pixels que diferem do fundo modal, por região, em
`depois_claro_1920x1080_*` (`medidas.py regiao`):

| região | tamanho | área | tinta |
|---|---|---|---|
| barra de ferramentas do visor | 817×128 | 104,6 kpx | **38,15 %** |
| grupo "Cabeçalhos do PGN" | 258×872 | 225,0 kpx | 26,98 % |
| tela do visor de PDF | 814×780 | 634,9 kpx | 36,21 % |
| **painel da Galeria (grade de diagramas)** | 798×645 | **514,7 kpx** | **0,24 %** |
| **editor da aba Texto (estado vazio)** | 1060×880 | **932,8 kpx** | **0,57 %** |
| **abaixo da tabela da aba Revisão** | 1063×385 | **409,3 kpx** | **0,00 %** |
| caixa vazia no topo de Resultado | 1056×138 | 145,7 kpx | 1,54 % |
| vazio abaixo dos controles de Resultado | 1065×175 | 186,4 kpx | 0,57 % |

**A barra de ferramentas é 159× mais densa que o painel que ela comanda** (38,15 % / 0,24 %).
A confirmação da primeira impressão da coordenação é literal: duas (na verdade **quatro**)
filas apertadas em cima de meio milhão de pixels vazios.

O 0,00 % da Revisão não é arredondamento: são **409 300 pixels sem um único pixel de tinta**.
O C3 reprovou a F7 por comprar uma métrica com 37 % de branco. Aqui são **99,76 %** na Galeria
e **99,43 %** no Texto.

E o vazio **premeditado**: a moldura do tabuleiro. Componente conexo `#312e2b` isolado
(`cv2.connectedComponentsWithStats`):

| captura | painel do tabuleiro | tabuleiro | tabuleiro / painel | marrom inerte |
|---|---|---|---|---|
| `depois_claro_1920x1080_resultado` | 935×450 = 420,8 kpx (**20,3 % da janela**) | 442×442 | 46,4 % | **225,4 kpx = 10,9 % da janela** |
| `depois_escuro_1920x1080_resultado` | 935×425 = 397,4 kpx | **417×417** | 43,8 % | 223,5 kpx |
| `depois_claro_1920x1080_estudo` | 679×775 = 526,2 kpx | 560×560 | 59,6 % | 212,6 kpx |
| `depois_claro_1280x800_resultado` | 574×308 = 176,8 kpx | 300×300 | 50,9 % | 86,8 kpx |

Numa janela clara de 1920×1080, **o tabuleiro ocupa 9,4 % da tela e o tapete marrom-escuro
decorativo ocupa 10,9 %. O tapete é maior que o tabuleiro.** Em uma ferramenta de edição de
xadrez.

Pior: **o mesmo objeto tem duas geometrias.** Em Resultado o tabuleiro fica centrado num
tapete que sobra 246 px de cada lado; em Estudo ele encosta na borda esquerda com folga de
~48 px. Duas abas do mesmo programa desenham o mesmo tabuleiro de dois jeitos.

E o custo da pele escura: **442 px de tabuleiro na pele clara, 417 px na "Foco"** — a fila de
pílulas do topo consome 34 px de altura da janela e o tabuleiro paga **11 % da própria área**.
A pele desenhada para foco entrega menos superfície de trabalho.

### 5. Cor como sinal — **SOBREVIVE. É o melhor item da frente.**

Medido em `depois_claro_1920x1080_galeria.png` (`medidas.py cores`): 24 858 cores distintas,
mas apenas **6 famílias de matiz** com saturação > 0,15 e passo de 15°:

| matiz | % da tela | o que é |
|---|---|---|
| 45° / 30° | 2,95 % / 1,62 % | o sépia da digitalização — **documento**, não cromo |
| 210° | 0,33 % | azul: primário, foco, seleção, régua |
| 60° | 0,14 % | amarelo do marcador |
| 0° | 0,14 % | vermelho: destrutivo |
| 240° | 0,06 % | o azul da marca d'água da DIGAR, no PDF |

**O cromo gasta 0,53 % da tela em cor, e gasta em estado.** Azul = interativo/selecionado,
vermelho = destrutivo, e nada mais. Isso é disciplina de ferramenta profissional, e é
exatamente o que a referência faz. Ponto para o construtor.

Uma ressalva menor, não bloqueante: o azul faz cinco trabalhos ao mesmo tempo (face do
primário, anel de foco, trilho preenchido da régua, marca da caixa de seleção, faixa de
seleção). Na prancha `amostrario_claro.png` a régua com foco tem **um anel azul em volta e um
trilho azul dentro**, a 4 px de distância — o D10 afastou os dois, mas eles continuam sendo o
mesmo azul, e "está com foco" lê igual a "está no máximo".

### 6. Tipografia da interface — **NÃO SOBREVIVE. E este é o defeito mais fácil de consertar.**

Censo de `QWidget.font()` sobre **todos** os widgets visíveis, nas duas peles (`sonda.py tipografia`):

| pele | widgets visíveis | tamanhos | famílias | pesos | combinações distintas |
|---|---|---|---|---|---|
| clássica | 104 | **12 px (101) · 11 px (3)** | 1 | **400 (104)** | **2** |
| foco | 111 | 12 px (108) · 11 px (3) | 1 | 400 (111) | 2 |

O sistema de tipos **existe**: `tipografia` declara quatro papéis — `TITULO` 10 pt/700,
`CORPO` 9 pt/400, `AUXILIAR` 8 pt/400, `DADO` 9 pt/400 Consolas (verificado em `sonda.py tipografia`).
**E ele não é usado.** Os três widgets a 8 pt são, os três, rótulos da barra de status. O papel
`TITULO` (10 pt **negrito**) aparece em **zero** widgets visíveis nas seis abas — o único
`setFont(TITULO)` do tronco está em `qt/legenda.py:70`, uma legenda de atalhos que não está em
nenhuma das 24 capturas.

Consequência, e ela é a resposta ao "parece um Qt demo": o rótulo do menu, o rótulo da aba, o
rótulo do botão, o **título do grupo** ("Filtros", "Cabeçalhos do PGN", "Este diagrama",
"Lances", "Reconhecido"), o **cabeçalho de coluna** da tabela, o **dado** da tabela, o
estado vazio e a barra de status são **todos 12 px, peso 400, uma família, sem versalete, sem
caixa alta, sem cor de apoio**. Uma diferença de 1 px em 12 (8 %) não produz hierarquia. Não há
um único elemento em negrito ou em corpo maior em nenhuma das seis abas.

Affinity, Resolve e Scrivener separam título de painel, rótulo de campo, valor e legenda por
**tamanho, peso, caixa e cor ao mesmo tempo**. Aqui os quatro são a mesma coisa.

### 7. Controles — **SOBREVIVE COM RESSALVA**

Medido por censo de bordas (`censo2.py`, seis abas claras a 1920):

| grandeza | resultado |
|---|---|
| altura de botão / campo / escolha / régua | **26 px em 197 de 214 controles** (92 %) |
| outras alturas | 24 (27×) · 27 (8×) · 28 (15×) · 30 (12×, os campos do grupo PGN) |
| indicadores de caixa e rádio | 16 / 18 px |
| raio de canto | `raio = espaco.minima()` = **2 px**, um só valor, aplicado em botão, campo, escolha, aba, grupo, barra de rolagem e progresso |
| peso de borda | **1 px em repouso, 2 px em foco**, dois valores, sem exceção |
| cor de borda | `CONTORNO_DE_CROMO` (`#707781` / `#959ca3`) em repouso, `SEPARADOR` no desabilitado |

Isso é consistente e eu o registro como tal. A ressalva: **a faixa 24–30 px em coisas que
deveriam ter uma altura só** — os campos do grupo "Cabeçalhos do PGN" têm 30 px enquanto os
botões ao lado têm 26. Numa coluna de 11 campos empilhados, 4 px de diferença em relação ao
botão "Gravar" logo abaixo é visível.

Ressalva maior, e ela é de desenho e não de medida: **o raio de 2 px é indistinguível de canto
reto.** Amostrei o canto superior esquerdo de um botão em `amostrario_claro.png`: um único
pixel de mistura (`#8d939b`) entre a borda e o fundo. Botão retangular de canto vivo com
filete de 1 px é a assinatura do Fusion do Qt, e é o que faz a janela ler como demo.

### 8. Estados vazios — **NÃO SOBREVIVE**

Quatro estados vazios, medidos:

1. **Galeria** — 798×645 px (514,7 kpx) com **duas** mensagens centradas, 321 px uma da outra:
   "varra o livro para ver os diagramas" (y=299) e "nenhum diagrama varrido" (y=620). Duas
   frases dizendo a mesma coisa, sem botão, sem ilustração, sem atalho — e **em duas cores
   diferentes**: amostrei o núcleo dos glifos e a primeira é `#555555` (`TEXTO_SECUNDARIO`)
   enquanto a segunda é `#000000` (`TEXTO_PADRAO`). Dois papéis de texto para a mesma
   mensagem, no mesmo painel. O botão que resolve — "Varrer o livro" — está a 645 px de
   distância, no topo.
2. **Texto** — o D8 foi marcado "corrigido". O conserto foi **uma linha de dica** de 11 px num
   vazio de 932,8 kpx. A densidade de tinta subiu de ~0 % para **0,57 %**. Ver o defeito
   bloqueante nº 3: **a linha nova está cortada** em toda janela abaixo de ~1350 px.
3. **Resultado** — a `QListWidget` de 1059×140 do §2.1: **zero palavras**, com anel de foco.
   A frase que orienta ("Nenhum diagrama aberto. Clique num diagrama marcado da página…")
   está 480 px abaixo, embaixo do tabuleiro.
4. **Revisão** — 409,3 kpx a **0,00 %** de tinta abaixo da fila, sem estado nem mensagem.

Carta §3.3, "Estado vazio sem orientação": item 1 tem orientação em prosa mas nenhuma ação;
o item 3 não tem nem prosa.

### 9. A pele escura — **SOBREVIVE. Reproduzido, e é honesto.**

Este eu remedi do zero, sem rodar o teste do construtor (script próprio sobre
`ui/tokens.cor(papel, cromo_escuro=...)`), e as três afirmações se sustentam:

1. **A elevação inverte de sentido.** `SUPERFICIE_AFUNDADA` L=0,9467 > `SUPERFICIE_PADRAO`
   L=0,8714 na clara; L=0,0085 **<** L=0,0151 na escura. Uma inversão mecânica preserva a
   ordem; esta não preserva. Confirmado nos cinco papéis de superfície.
2. **A matiz sobrevive.** Sobre os papéis semânticos com saturação real o desvio máximo é
   **1,18°** (`REALCE_VARIANTE`); `SELECAO` 1,14°, `BOTAO_PRIMARIO` 0,21°, `PROBLEMA_TEXTO`
   0,14°. (Meu filtro mais frouxo pegou `SUPERFICIE_ELEVADA` a 24°, mas é um cinza quase
   neutro em que matiz não significa nada — a afirmação do construtor é sobre os papéis com
   matiz, e ela está certa.)
3. **Nenhum papel é o negativo exato.** Testei `255−c` canal a canal com tolerância de 2 %
   sobre os 56 papéis: **nenhuma violação**.
4. E os **25 papéis que não mudam** entre as peles são exatamente os de documento (casas,
   glifos, molduras, setas, marcações) — a decisão declarada da S-224, e ela é coerente.

A paleta escura é **projetada**. Digo isso sem reservas.

O que **não** é projetado é o *arranjo* da pele "Foco": ela acrescenta uma fila de quatro
pílulas no topo cujas ações são **duplicatas de botões visíveis na mesma tela** —
"Aplicar a FEN digitada" também existe em `(911, 800)`, "Salvar a posição" em `(65, 861)` e
"OCR todos diagramas" em `(1705, 77)`. Três de quatro. E são os **únicos quatro botões com
ícone da aplicação inteira** — todo o resto é texto puro. Uma família de ícones que aparece em
exatamente uma fila é a definição de "ícones de origens diferentes misturados" (§3.3).

---

## §3 — Reverificação dos portões (carta §6)

Rodei tudo. **Cinco das seis linhas reproduzem.** Onde o número do construtor está certo, eu
digo que está certo.

| portão | relatório | minha medição | veredito |
|---|---|---|---|
| Contraste WCAG AA, 100 % dos pares, 2 peles | 286 pares, 212 sob portão, 0 reprovados | **idêntico**: 286 / 212 / 0 nas duas; folga mínima 3,27:1 (clara) e 3,03:1 (escura) | **CONFIRMADO** |
| Pan/zoom ≥ 55 fps | 78,0 fps @ p95 (mediana de 4 invocações) | **3 invocações: 87,3 · 84,1 · 86,9 → mediana 86,9**; zoom 66,0 · 66,4 · 66,6 → **66,4** | **CONFIRMADO, e o construtor foi conservador** |
| Teclado + nome + papel | 256/256, 0 sem nome, 0 sem papel, 6/6 | **idêntico** por execução do arnês… | **CONFIRMADO no número, REFUTADO no significado — ver bloqueante nº 1** |
| Tema escuro projetado | 18 asserções | remedi as três propriedades do zero: todas se sustentam | **CONFIRMADO** |
| Nada bloqueia a thread > 16 ms | REPROVA: 244 ms / 178 ms | REPROVA: **245 / 246 / 261 ms** ao abrir; **163–206 ms** por virada | **CONFIRMADO na falha, REFUTADO no diagnóstico — bloqueante nº 5** |
| Progresso nunca indeterminado | REPROVA: 1 operação | REPROVA: 1 indeterminada **e 2 sem cancelamento** | **CONFIRMADO, mas o relatório reporta metade** |

### 3.1 A alegação que carrega a ADR-0009 — **VERIFICADA INDEPENDENTEMENTE**

Esta é a que a coordenação pediu para conferir especificamente, e ela se sustenta em três
provas, todas minhas:

1. `\.venv\Scripts\python.exe -m pytest tests/unit/ui/ -q` → **`83 passed in 0.47s`**.
2. O venv da suíte **não tem binding de Qt**: `importlib.util.find_spec` devolve `None` para
   `PyQt6`, `PyQt5`, `PySide6`, `PySide2`, `wx`, `gi`, `kivy`.
3. Varredura AST própria (não o teste do construtor) sobre **58 módulos** de
   `ChessVisionOFF_Puro/src/chess_diagram_ocr/ui/`: **zero** `import` de toolkit e zero de
   `chess_diagram_ocr.qt`. E importar `ui.folha_de_estilo` deixa `sys.modules` **sem nenhum**
   módulo de toolkit.

**A fronteira é real e o portão de contraste roda de verdade sem Qt.** É a melhor coisa desta
frente e ela deve sobreviver a qualquer refatoração futura.

---

## §4 — Defeitos bloqueantes

### 1. O portão de teclado reporta "0 sem nome" porque mede `bool(nome)`, e não "o nome nomeia". 34 de 256 controles (13,3 %) são anunciados por nada.

**Onde:** `benchmarks/reports/ui/teclado.json`, campo `ordem_do_tab`, nas seis abas.

**O que:** extraí os 256 nomes acessíveis e filtrei os que não contêm três letras seguidas ou
que são o nome genérico da classe:

| aba | nº na ordem | classe | nome acessível |
|---|---|---|---|
| **as 6 abas** | #7 | `QSpinBox` | **`"121"`** — o **valor atual** vira o nome |
| **as 6 abas** | #9, #10 | `QPushButton` | **`"-"`** e **`"+"`** |
| Estudo, Galeria | #31–34, #27, #30 | `QPushButton` | `"|◀"`, `"◀"`, `"▶"`, `"▶|"` |
| **Texto** | #29, #30 | `QComboBox` | **`"Escolha"`** |
| **Dataset** | #27, #28, #29 | `QComboBox` | **`"Escolha"`** (três iguais) |
| Dataset | #35, #36 | `QPushButton` | `"<"`, `">"` |
| Resultado | #23 | `QListWidget` | **`"Lista"`** |
| Estudo | #46 | `QPushButton` | `".md"` |

O relatório §5.2 diz: *"Antes eram 40 controles sem nome nenhum… O Qt anunciava cada um pelo
tipo: 'caixa de edição', sem dizer qual."* **Cinco caixas de escolha continuam sendo anunciadas
pelo tipo** — `"Escolha"` — e três delas na mesma aba, indistinguíveis entre si. O `QListWidget`
mais proeminente da aba Resultado é `"Lista"`.

E o caso do `QSpinBox` é **pior que não ter nome**: a cascata cai em `text()`, que num spinner
devolve o valor. O leitor de tela anuncia "121, 121" e o **nome do controle muda quando o
usuário vira a página**. A identidade do objeto é o seu conteúdo.

**Como reproduzir:** `python -c` sobre `teclado.json`, regex `^\s*\d+\s+(\w+):\s*(.*)$` na
lista `ordem_do_tab`, filtrando `not re.search(r'[A-Za-zÀ-ÿ]{3}', nome)`.

**Por que reprova:** o portão do SPEC §11.3 é *"nome e papel em todo controle"*. Um nome que
não nomeia não cumpre o portão; a métrica foi comprada redefinindo "tem nome" como "a string
não é vazia". É o mesmo movimento que o C3 reprovou na F7.

### 2. Um nome de livro de 149 caracteres — que já está na pasta `PDF/` do projeto — desenha dois botões um por cima do outro, corta o rótulo fora da janela e sobe o piso da janela para 1513 px.

**Onde:** barra do visor, qualquer aba. Reproduzido com
`PDF/Gaprindashvili, Paata - Imagination in Chess. How To Think Creatively And Avoid Foolish Mistakes (Bastford, 2005) 2p 145p_OCR_Aprimorar_Aprimorar.pdf`
(149 caracteres). Captura: `benchmarks/reports/critique/ui/c1_titulo_longo_1920.png` e o
recorte a 2× `z_titulo_longo_barra.png`.

**O que**, com a janela a **1920×1080** — não em tela pequena, na tela grande:

| medida | com "1937 Kemeri.pdf" | com o título de 149 chars |
|---|---|---|
| `minimumSizeHint().width()` | 1243 | **1513** |
| controles fora da janela | 0 | **1** — o `QLabel` do título, `x=1094 w=906` → termina em **x=2000** numa janela de 1920 |
| pares de controles sobrepostos > 40 px² | 1 (o `QLineEdit` interno do `QSpinBox`, normal) | **4** |

O pior par: **`QPushButton "Cancelar exportação"` em (1094, 116) sobreposto a
`QPushButton "Página anterior"` em (1094, 120), com 2310 px² de interseção — 67 % da área do
próprio botão (133×26 = 3458 px²).** No PNG, "Cancelar exportação" **não aparece**: está
desenhado por baixo. O botão continua `isVisible() == True`, continua na cadeia do `Tab` e
continua contando nos 256 do portão de teclado.

O rótulo é cortado **no meio da palavra**, sem reticências: a barra mostra
`…_OCR_Aprimorar_Aprimora` e os caracteres `r.pdf` simplesmente não são desenhados.

E `minimumSizeHint` sobe para 1513 px: **o nome do arquivo determina a largura mínima da
aplicação.** Num monitor de 1366 px de largura, abrir este livro deixa a janela 147 px mais
larga que a tela, sem recuo possível.

**Como reproduzir:** `benchmarks/reports/critique/ui/sobreposicao.py`.

**Por que reprova:** carta §3.3, primeiro item — *"Qualquer texto cortado, **sobreposto** ou
com reticências onde caberia"*. Duas violações no mesmo lugar. E a ação escondida é o
**cancelamento de uma exportação longa**, que é o §3.3 "Operação longa sem cancelamento" por
via indireta: o botão existe, o usuário não o vê.

### 3. O conserto do D8 — a dica do estado vazio da aba Texto — está ele próprio cortado em toda janela abaixo de ~1350 px, inclusive no tamanho mínimo.

**Onde:** `depois_claro_1280x800_texto.png`, `depois_escuro_1280x800_texto.png`, e minhas
capturas `c1_{claro,escuro}_1024x768_texto.png` (1243×890 / 1243×924).

**O que:** medido em `sonda.py dica` com a `QFontMetrics` do próprio editor:

| janela | viewport do editor | a dica pede | cabe | resultado |
|---|---|---|---|---|
| 1920 | 1057 px | 765 px | 1049 px | ok |
| 1280 | 696 px | 765 px | 688 px | **cortada em 77 px** |
| **1243 (mínimo)** | 696 px | 765 px | 688 px | **cortada em 77 px** |

Na tela o usuário lê: *"Nenhuma folha lida. Use "Ler folha" para transcrever a página aberta
no visualizador, ou "Achar no texto…" para procurar"* — **e acaba ali**. As palavras
`numa folha já lida.` nunca aparecem, e não há reticências, porque o Qt não elide nem quebra
`placeholderText` de um `QPlainTextEdit`.

**Não existe tamanho de janela abaixo de ~1350 px em que a frase seja legível inteira**, e o
piso da janela é 1243. A correção de um defeito de texto cortado introduziu um defeito de
texto cortado.

**Por que reprova:** §3.3, primeiro item, de novo — e desta vez no artefato que o relatório
apresenta como prova de que o D8 foi resolvido.

### 4. A janela recusa 1366×768. De 13 % a 37 % dos controles de cada aba ficam abaixo da borda inferior da tela, sem barra de rolagem.

**Onde:** toda a aplicação. Medido em `casos_ruins.py`.

**O que:**

```
[claro]  minimumSizeHint = 1243x890
[claro]  pedido 1024x768  -> ficou 1243x890  RECUSOU
[claro]  pedido 1366x768  -> ficou 1366x890  RECUSOU
[claro]  pedido  800x600  -> ficou 1243x890  RECUSOU
[escuro] minimumSizeHint = 1243x924   (as três recusas idênticas)
```

Num laptop de 1366×768 com barra de tarefas (~730 px úteis), a janela fica **160 px** (clara)
ou **194 px** (escura) mais alta que a tela. Contei os controles cuja base cai abaixo de
y = 730:

| aba | claro | escuro |
|---|---|---|
| Resultado | 6 de 32 (18,8 %) | 11 de 36 (30,6 %) |
| Estudo | 7 de 50 (14,0 %) | 7 de 54 (13,0 %) |
| Galeria | 9 de 47 (19,1 %) | 9 de 51 (17,6 %) |
| Texto | 6 de 37 (16,2 %) | 6 de 41 (14,6 %) |
| **Dataset** | **12 de 36 (33,3 %)** | 12 de 40 (30,0 %) |
| **Revisão** | **11 de 30 (36,7 %)** | 11 de 34 (32,4 %) |

Na Revisão o que fica fora é **`Corrigir agora`, `Marcar revisado`, `Pular`, `Reabrir`,
`Próximo pendente`** — o fluxo inteiro da aba, incluindo a primária. No Dataset é
`Abrir no editor`, `Conferir com o modelo`, `Quarentena`, `Remover` e o paginador. E a barra
de status em todas.

**Por que reprova:** a carta §3.2 nomeia explicitamente *"A janela redimensionada para 800×600"*
como caso obrigatório. A janela não faz 800×600, não faz 1024×768 e não faz 1366×768. O
relatório registra isto como D14 severidade "A", adiado, com a causa isolada
(`painel_da_galeria.py:268 setFixedSize(420, 420)`). A causa está certa; a severidade não. Uma
ferramenta profissional cuja ação primária fica fora da tela na segunda resolução de laptop
mais comum do mundo não é utilizável nessa máquina.

### 5. O relatório diagnostica errado a própria falha que admite: a pior pilha do "abrir PDF" não é o PyMuPDF, é leitura de CSV — e o conserto proposto em §7.1 não a alcança.

**Onde:** `caissa.ui.audit.bloqueio`, operação `abrir PDF (load_pdf, 1a pagina a 300 DPI)`.

**O que:** o §6.2 afirma *"A pilha do pior é inequívoca e sempre a mesma"* e mostra
`painel_do_pdf.py → pdf_io.render_pdf_page → get_pixmap → fz_run_display_list`. Rodei o arnês
**três vezes**. Nas **três**, a pilha do pior travamento do `abrir PDF` (245,0 / 246,2 /
260,5 ms) é:

```
janela.py:983  abrir_pdf
painel_do_pdf.py:386  load_pdf
janela.py:948  _abriu_livro
janela.py:977  _carregar_marcas_salvas
labels.py:357  read
labels.py:353  read_rows
labels.py:380  _load_rows
csv.py:111     __next__
```

**Não é rasterização. É `csv` no laço de eventos.** O §7.1 propõe submeter a rasterização a
uma `Tarefa` e chama isso de "o maior débito". Esse conserto resolve as viradas de página
(163–206 ms) e **não toca nos 245 ms de abertura**, que é o número maior e o que o §0 publica
como o titular do portão reprovado.

**Por que reprova:** carta §6, honestidade de medição. O número está certo, a pilha publicada
não é a que o instrumento devolve, e o plano de conserto foi escrito contra a pilha errada.

### 6. A aba Dataset trava a interface por 1,3 segundo na primeira vez que é aberta. O arnês reporta 14,6 ms e diz `viola: False`, porque tira a mediana de três execuções e só a primeira é fria.

**Onde:** `bloqueio_*.json`, operação `aba Dataset: mostrar e carregar as amostras`.

**O que**, campo `pior_ms_por_execucao` nas minhas três invocações:

| invocação | execução 1 (fria) | execução 2 | execução 3 | **mediana publicada** | `viola` |
|---|---|---|---|---|---|
| 194639 | **1244,4 ms** | 13,3 | 14,6 | 14,6 | `False` |
| 194727 | **1447,3 ms** | 15,8 | 15,4 | 15,8 | `False` |
| 194737 | **1302,2 ms** | 15,5 | 17,7 | 17,7 | `False` |

Mediana das três primeiras execuções: **1302 ms — 81× o portão de 16 ms.** A pilha é sempre
`painel_do_dataset.py:285 showEvent → _reler_agora → dataset_browser.load_rows → labels.read → csv`:
o primeiro clique na aba lê um CSV de 5 431 linhas na thread da interface.

O §6.2 descreve esta operação como *"ela carrega 5.431 amostras e fica **na fronteira** dos
16 ms"*. Não fica. Fica em 1,3 s no único caso que um usuário real vive — o primeiro clique
depois de abrir o programa. As execuções 2 e 3 medem o cache do sistema de arquivos.

**Por que reprova:** carta §3.3, *"Qualquer congelamento de interface, mesmo de meio segundo"* —
e a metodologia do arnês (mediana de três execuções consecutivas) é **estruturalmente cega ao
custo de primeiro uso**, que é o custo que importa. Este defeito não aparece em lugar nenhum
do relatório.

### 7. Duas operações longas sem cancelamento, não uma — e o próprio arnês não consegue nomear duas das suas linhas.

**Onde:** saída de `caissa.ui.audit.progresso`.

**O que:** o §0 do relatório publica *"REPROVA: 1 operação (detecção de duplicatas)"*. A saída
do arnês, que reproduzi, diz:

```
DEFEITOS BLOQUEANTES (1): total conhecido, barra indeterminada
  - detecção de duplicatas  (qt/painel_do_dataset.py:523)

Operacoes longas sem cancelamento (2):
  - detecção de duplicatas  (qt/painel_do_dataset.py:523)
  - nome  (qt/painel_de_texto.py:1097)
```

A segunda operação sem cancelamento — `qt/painel_de_texto.py:1097` — **não é mencionada em
nenhum lugar do relatório**. E o inventário lista **duas** operações cujo rótulo é literalmente
a string `"nome"` (`painel_da_galeria.py:460` e `painel_de_texto.py:1097`): o instrumento que
existe para nomear os defeitos não consegue nomear dois dos seus próprios itens.

**Por que reprova:** §3.3, *"Operação longa sem cancelamento"* é item que reprova sozinho, e o
relatório reporta metade da contagem que o próprio instrumento devolve.

### 8. A prancha de controles rotula um botão "Com foco" e mostra um botão sem foco — e não mostra `hover` nem `pressed` em lugar nenhum.

**Onde:** `benchmarks/reports/ui/amostrario_claro.png` e `amostrario_escuro.png`;
`src/caissa/ui/audit/amostrario.py:79-90` e `:162`.

**O que:** diferenciei pixel a pixel o retângulo do botão "Abrir PDF" (normal, x 30–212) contra
o do botão "Com foco" (x 218–400) nas duas peles. **A única diferença são os glifos do rótulo.**
A borda esquerda é `#707781` nos dois (clara) e `#959ca3` nos dois (escura). Não há anel.

A causa está no código do próprio arnês: a linha 90 faz `com_foco.setFocus()`, e a linha 162
faz `regua_com_foco.setFocus()` — o último `setFocus` vale. O construtor **sabia**: o comentário
da linha 161 diz *"O foco vai para a régua no fim: `setFocus` no fim de `montar` é o último a
valer."* E deixou o botão rotulado "Com foco" na prancha publicada.

Além disso, o cabeçalho da prancha é *"Botões — normal · foco · desabilitado · ênfase"*:
**`hover` e `pressed` não estão lá**. São exatamente os dois estados em que estavam os itens 1,
2 e 4 da tabela de correções de contraste do §3.3 do relatório. Os números daqueles estados
foram afirmados e **nunca desenhados**.

Reconstruí a prancha que faltava (`benchmarks/reports/critique/ui/estados.py` →
`c1_estados_{claro,escuro}_foco{0,1,2}.png`, 3 papéis × 5 estados) e o resultado, medido, é
que os estados **existem** e são perceptíveis — ver §5, item 1, onde eu digo isso. O defeito é
o artefato: **a prancha que a carta §3.1 manda olhar afirma no rótulo algo que a imagem não
contém.**

**Por que reprova:** §3.1 — *"Não confie na descrição do construtor. Rode. Abra. Amplie."* Um
crítico que confie nesta prancha conclui que o anel de foco de botão não existe. Uma prova
errada é pior que prova nenhuma.

---

## §5 — Defeitos não bloqueantes

1. **`hover` e `pressed` existem e são perceptíveis.** Registro como crédito, porque cheguei a
   suspeitar do contrário. Medido a partir dos tokens: a face muda com razão de luminância de
   1,19 a 1,31 no `hover` e 1,31 a 1,56 no `pressed`, com ΔRGB de 23 a 41. É feedback real.
2. **Mas o `pressed` clareia na pele escura**: `PRIMARIO` `#6ea8fe → #98c1fe` e `DESTRUTIVO`
   `#e4665d → #ec928c`. Um botão destrutivo pressionado fica **mais pálido e menos saturado**
   que em repouso, o que lê como "recuando / inativo" — o oposto da affordance. A regra
   `afastar` foi escolhida para o contraste do **rótulo** e produz a direção errada para a
   **face**. Toda a referência escurece no `pressed` nas duas peles.
3. **O anel de foco tem três cores conforme o papel do botão**: `#0b5ed7` no neutro, `#ffffff`
   no primário claro, `#141013` no primário escuro (medido no perfil de borda das minhas
   capturas `c1_estados_*_foco*.png`). A justificativa do construtor é boa (`FOCO` sobre face
   saturada dá 1,15:1) mas a solução da referência é um anel **deslocado** para fora do
   controle, mantendo uma convenção só.
4. **`#555555` faz três trabalhos na pele clara**: rótulo de botão desabilitado, texto de
   estado vazio e rótulo de aba não selecionada — todos `#555555` sobre `#f0f0f0`, 6,54:1
   (medido no pixel em `contraste_no_pixel.py`). O contraste passa; a semântica colide.
5. **A caixa de seleção marcada é um quadrado azul cheio sem símbolo, e a tri-estado é um
   quadrado cinza cheio.** As duas diferem **apenas por matiz** — mesma forma, mesmo tamanho,
   mesmo preenchimento. WCAG 1.4.1 (Uso de Cor, nível **A**) pede que cor não seja o único meio
   visual. O portão do construtor mede 1.4.3 e 1.4.11 e não cobre 1.4.1.
6. **Colunas constantes na tabela do Dataset**: "Livro", "Pag." e "Criado em" mostram `—` em
   todas as 5 431 linhas, e "Legalidade" mostra `legal` em todas as visíveis. Quatro de oito
   colunas não carregam informação; a coluna "Motivo" da Revisão, que carrega, é a elidida.
7. **A coluna "Motivo" da Revisão está elidida em 14 das 27 linhas a 1920 e em 27 de 27 a
   1280.** É o texto que diz por que o item está na fila.
8. **`Cancelar exportação` e `Limpar os headers` nascem desabilitados** e, sendo `DESTRUTIVO`
   no segundo caso, perdem toda a cor — um destrutivo desabilitado fica pixel a pixel igual a
   um neutro desabilitado. Decisão declarada e defensável; registro porque o usuário perde a
   informação de que aquela ação é perigosa antes mesmo de poder usá-la.
9. **`.md`, `.html`, `.rtf` como três botões de barra** na aba Estudo. É um seletor de formato
   de exportação ocupando três posições de barra permanentes.
10. **`Modo bloco (lento)`** — uma caixa de seleção na barra principal cujo rótulo admite que a
    opção é lenta, sem dizer quanto nem quando usá-la.
11. **A prancha `amostrario_*` mostra o texto do `QProgressBar`** (`37%`) que o produto esconde
    (`qt/rodape.py:126`). A 50 % de avanço esse texto cairia sobre `#0a58ca` e daria **3,14:1**,
    abaixo do piso de texto. Declarado pelo construtor no §7.5; confirmo a aritmética.
12. **Alturas de controle 24 / 26 / 27 / 28 / 30 px** — 92 % em 26, mas os campos do grupo
    "Cabeçalhos do PGN" a 30 px ficam 4 px mais altos que o botão "Gravar" imediatamente abaixo.

---

## §6 — O que funciona, e merece sobreviver ao próximo ciclo

A carta §5.5 manda nomear o que funciona. Nomeio, e não é pouco:

1. **A fronteira `ui/` × `qt/` é real e verificável.** 58 módulos varridos por AST própria,
   zero imports de toolkit, 83 testes verdes em 0,47 s num venv sem nenhum binding de Qt. O
   portão de contraste do §11.3 é hoje afirmável por teste em qualquer máquina. Esta é a
   contribuição arquitetural da frente e ela é sólida.
2. **O checador de contraste não é uma lista escrita à mão.** Ele resolve a cascata do QSS para
   descobrir sobre que fundo cada `color:` cai, e `test_cascata.py` afirma o motor contra
   folhas mínimas. Um componente novo vira par novo sem ninguém escrever uma linha. Isso é
   engenharia de portão de verdade, e é raro.
3. **Os 286 pares passam, e os pixels concordam.** Amostrei 22 pares de letra/fundo
   **renderizados** (não declarados) nas duas peles: mínimo 5,71:1, e as marcações apertadas
   estão exatamente onde o relatório disse.
4. **A paleta escura é projetada, não invertida**, e eu remedi as três propriedades do zero.
5. **A disciplina de cor é de ferramenta profissional**: seis famílias de matiz na tela, das
   quais duas são o papel digitalizado; o cromo gasta 0,53 % da tela em cor e gasta em estado.
6. **A escala de espaço existe como dado e o código a obedece** — nenhum `setSpacing` literal em
   todo `qt/`.
7. **O antes/depois é uma melhoria genuína.** Comparei `antes_escuro_1280x800_{galeria,estudo}`
   com os `depois_*`: os tofus `⏮`/`⏭`, as caixas de seleção sem indicador, os campos sem borda
   na pele escura e as barras de rolagem brancas de 12 px eram reais e sumiram.
8. **O construtor reportou honestamente os dois portões que falham**, com número, pilha e
   caminho de conserto, em vez de escondê-los. Isso é o comportamento certo e deve continuar.

O problema não é que o trabalho seja fraco. É que **o trabalho feito foi de acessibilidade e
de conformidade, e o pedido era de desenho.** Passar em 100 % do WCAG e parecer um Qt demo são
alegações independentes, e a segunda não foi atacada.

---

## §7 — O que precisa mudar para eu aprovar

Ordem de serviço numerada, medível. Cada item tem um número de partida (medido acima) e um
número de chegada.

### Bloqueantes — sem estes não há segundo ciclo

1. **Nomeie os 34 controles que hoje se anunciam por nada.** Ponha `accessibleName` explícito
   em: o spinner de página (`"Página, 1 a 289"` — **nunca** derivado de `text()`, que é o
   valor), os pares `-`/`+` (`"Diminuir o zoom"` / `"Aumentar o zoom"`), os quatro botões de
   navegação (`"Primeiro diagrama"`, `"Diagrama anterior"`, `"Próximo diagrama"`, `"Último
   diagrama"`), as cinco `QComboBox` hoje chamadas `"Escolha"` e a `QListWidget` chamada
   `"Lista"`. Depois **acrescente o portão que falta ao arnês**: `teclado.py` deve reprovar
   quando o nome (a) coincidir com o nome genérico da classe em `PAPEL_POR_CLASSE`, (b) não
   contiver ao menos três caracteres alfabéticos, ou (c) se repetir dentro da mesma aba.
   *Alvo: 0 de 256 controles com nome não informativo, cobrado por teste.*

2. **Elida o rótulo do livro e tire-o do cálculo de largura mínima.** `setMinimumWidth(0)` +
   `QFontMetrics.elidedText(..., Qt.TextElideMode.ElideMiddle)` no `QLabel` do título, com o
   nome completo no `toolTip`. O título de 149 caracteres não pode mover
   `minimumSizeHint().width()` de 1243 para 1513.
   *Alvo: `minimumSizeHint` idêntico para qualquer nome de livro; zero controles fora da
   janela; zero pares sobrepostos acima de 40 px² (exceto o `QLineEdit` interno do `QSpinBox`),
   cobrado por `sobreposicao.py` como teste.*

3. **Faça a dica do estado vazio caber no piso da janela.** `placeholderText` de
   `QPlainTextEdit` não elide nem quebra. Troque por um **widget de estado vazio** de verdade
   (ver item 7) ou por um `QLabel` com `setWordWrap(True)` sobreposto ao editor.
   *Alvo: a frase inteira legível a 1243 px de largura.*

4. **Baixe o piso da janela para caber em 1366×768.** A causa já está isolada:
   `painel_da_galeria.py:268 setFixedSize(BOARD_VIEW_SIZE, BOARD_VIEW_SIZE)`. Troque por
   `setMinimumSize(240, 240)` + reescala do `QPixmap` no `resizeEvent`, e atualize
   `test_qt_painel_da_galeria.test_o_recorte_tem_o_lado_declarado`.
   *Alvo: `minimumSizeHint()` ≤ 1024×700 nas duas peles; zero controles abaixo de y=730 numa
   janela de 1366×768, cobrado pelo mesmo censo que usei.*

5. **Tire o `csv` das duas thread-de-interface, não só o rasterizador.** São **dois** consertos
   e o §7.1 só nomeia um:
   - `janela.py:977 _carregar_marcas_salvas` → `labels.read` (245 ms na abertura);
   - `painel_do_dataset.py:285 showEvent` → `dataset_browser.load_rows` (**1302 ms** no primeiro
     clique da aba).
   Os dois cabem no `qt/trabalho.Tarefa` que já existe, sem tocar no contrato síncrono de
   `desenhar_pagina` — são leituras de disco, não rasterização.
   *Alvo: nenhuma operação acima de 16 ms **na execução fria**.*

6. **Conserte a metodologia do arnês de bloqueio antes de conseguir o item 5.** `bloqueio.py`
   deve reportar `max(pior_ms_por_execucao)` **e** a mediana, e `viola` deve olhar o **pior**,
   não a mediana — senão o item 5 pode ser declarado resolvido com a aba Dataset ainda
   travando 1,3 s no primeiro clique. Acrescente uma execução explicitamente fria (cache
   invalidado) para as operações que leem disco.

7. **Ponha cancelamento nas duas operações longas, não em uma**, e publique a contagem que o
   arnês devolve. `qt/painel_do_dataset.py:523` (detecção de duplicatas, também determinada) e
   `qt/painel_de_texto.py:1097`. E dê rótulo aos dois itens do inventário que hoje se chamam
   `"nome"`.

8. **Refaça a prancha de controles.** Uma captura por estado de foco (o Qt só tem um foco), e
   acrescente as colunas `hover` e `pressed` — os dois estados cujos números o §3.3 do
   relatório publica e cuja imagem não existe. Meu `estados.py` já faz isso e pode ser
   incorporado. *Alvo: 3 papéis × 5 estados × 2 peles, com o rótulo de cada célula batendo com
   o que a célula desenha.*

### De desenho — sem estes, passa no portão e continua parecendo um Qt demo

9. **Use a escala tipográfica que já existe.** Hoje: 104 widgets, **2 tamanhos (12/11 px), 1
   peso, 1 família**, com `TITULO` (10 pt/700) aplicado a **zero** widgets visíveis. Aplique
   `tipografia.TITULO` a todo `QGroupBox::title` e a todo cabeçalho de coluna
   (`QHeaderView::section`), e `tipografia.AUXILIAR` a todo texto de apoio (dica, contagem,
   unidade, estado vazio secundário). *Alvo mínimo: 3 tamanhos e 2 pesos presentes em cada aba,
   cobrado pelo censo de `QWidget.font()`; hoje o censo devolve 2 combinações distintas, o
   alvo é 5–6.*

10. **Uma ênfase por tela, não por barra.** Hoje Resultado, Estudo e Revisão desenham **três**
    botões primários simultâneos. Estenda `estilos.conferir_barra` para
    `conferir_tela(janela) -> no máximo 1 PRIMARIO visível`. As outras duas ações que hoje são
    primárias viram neutras com atalho declarado.

11. **Agrupe a barra do visor em 3–4 blocos nomeados e tire o resto de cena.** Hoje são
    **16 controles em 4 filas a 1920 e em 6 filas a 1243**, e medi que **14 dos 16 (88 %)
    trocam de fila entre 1920 e 1243** — a barra não tem mapa espacial, ela flui como texto.
    Blocos propostos: **[Livro]** `Abrir PDF` · título elidido · `Abrir no leitor`;
    **[Reconhecer]** `OCR melhor diagrama` (a única primária) · `OCR todos` · `Tirar a caixa` ·
    `Selecionar área`; **[Navegar]** `◀` · spinner · `▶` · `−` · `+` · ajuste;
    **[Exportar]** `Exportar PDF → PGN` · `Cancelar`. O bloco Exportar e as duas caixas de
    seleção (`Marcar diagramas`, `Roda vira a página`) vão para os menus `Ferramentas` e `Ver`
    — que **já estão povoados** (6 e 15 itens; `Estudo` tem 31 e `Texto` tem 48), o que torna a
    barra em boa medida uma segunda cópia deles. *Alvo: ≤ 2 filas a 1243 px; ≤ 2 de 16 controles
    trocando de fila entre 1920 e 1243; separador visível de 1 px entre blocos, porque 4 px de
    diferença de vão não é agrupamento.*

12. **Idem para a aba Estudo: 46 botões, 40 deles de peso idêntico, em 4 filas.** Colapse
    `Colar / Abrir PGN / .md / .html / .rtf / Para o texto` num único `Exportar ▾` com menu, e
    `Promover / Principal / Rebaixar / Apagar variante / Apagar daqui / Símbolo` num menu de
    contexto da árvore de lances — que é onde essas ações pertencem. *Alvo: ≤ 12 botões
    permanentes na aba, ≤ 2 filas.*

13. **Dê ao tapete do tabuleiro um teto proporcional.** Hoje o tapete `#312e2b` ocupa
    **10,9 % da janela de 1920×1080 contra 9,4 % do tabuleiro**. Ou o tabuleiro cresce
    (`MAX_DO_TABULEIRO = 560` deixa de ser um teto absoluto e passa a acompanhar o painel), ou
    o painel encolhe até o tabuleiro. E **unifique a geometria entre Resultado e Estudo**: hoje
    o mesmo objeto tem 46,4 % e 59,6 % de ocupação do painel. *Alvo: ocupação ≥ 80 % em ambas
    as abas, e a mesma em ambas ± 3 pontos.*

14. **Construa três estados vazios de verdade**, com título (`TITULO`), uma frase
    (`AUXILIAR`) e **o botão que resolve**, dentro do vazio:
    - Galeria (514,7 kpx a 0,24 %): título "Nenhum diagrama ainda", frase, botão
      `Varrer o livro` — o mesmo que hoje está a 645 px de distância. E **apague a segunda
      mensagem**: duas frases dizendo a mesma coisa a 320 px uma da outra.
    - Resultado: a `QListWidget` de 1059×140 não pode ficar vazia e com anel de foco. Ou ela
      recebe um estado vazio com a frase que hoje está 480 px abaixo, ou ela **colapsa a zero
      quando não há itens** e o foco inicial vai para o tabuleiro.
    - Revisão: os 409,3 kpx a 0,00 % abaixo da fila.
    *Alvo: nenhuma região de painel acima de 200 kpx com menos de 2 % de tinta.*

15. **Uma margem esquerda, não quatro.** Hoje as filas começam em x = 8, 9, 12 e 13 conforme a
    aba. *Alvo: um valor, derivado de `espaco.moldura()`, cobrado por teste de leiaute.*

16. **Escureça o `pressed` nas duas peles.** Hoje `PRIMARIO` escuro vai `#6ea8fe → #98c1fe` e
    `DESTRUTIVO` escuro vai `#e4665d → #ec928c` — pressionar clareia, o que lê como recuar.
    Mantenha a direção do `hover` (que resolve o contraste do rótulo) e inverta só o `pressed`,
    ou desloque o conteúdo em 1 px, que é o que a referência faz.

17. **Dê símbolo à caixa de seleção marcada.** Hoje "marcada" é um quadrado azul cheio e
    "indeterminada" é um quadrado cinza cheio: mesma forma, mesmo tamanho, só a matiz separa.
    WCAG 1.4.1 nível A. Um `✓` na marcada e um `–` na indeterminada resolvem, e o portão de
    contraste deve ganhar uma checagem de 1.4.1 junto.

18. **Suba o raio de canto de 2 px para 4–5 px** em botão, campo, escolha e aba. É a mudança de
    uma linha (`raio = espaco.minima()`) e é a diferença mais barata entre "widget do Fusion" e
    "controle desenhado". Meça: hoje o canto de um botão tem **1 pixel** de mistura.

---

## §8 — Como reproduzir tudo

```bash
# Fase 1 — composição (venv da suíte, sem Qt)
.venv\Scripts\python.exe benchmarks\reports\critique\ui\medidas.py cores  depois_claro_1920x1080_galeria.png
.venv\Scripts\python.exe benchmarks\reports\critique\ui\medidas.py regiao depois_claro_1920x1080_galeria.png \
    "galeria:8:85:806:730" "barra:1095:28:1912:156"
.venv\Scripts\python.exe benchmarks\reports\critique\ui\ritmo.py  depois_claro_1920x1080_estudo.png claro
.venv\Scripts\python.exe benchmarks\reports\critique\ui\censo2.py depois_claro_1920x1080_galeria.png claro
.venv\Scripts\python.exe benchmarks\reports\critique\ui\contraste_no_pixel.py depois_claro_1920x1080_galeria.png \
    "estado-vazio:310:292:500:307"

# Fase 2 — os portões (contraste e arquitetura no venv da suíte; o resto no do tronco)
.venv\Scripts\python.exe -m pytest tests\unit\ui\ -q
.venv\Scripts\python.exe -m caissa.ui.audit.contraste
.venv\Scripts\python.exe -m caissa.ui.audit.progresso
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado  --pdf "...\1937 Kemeri.pdf"
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.quadros  --pdf "...\1937 Kemeri.pdf"   # 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio --pdf "...\1937 Kemeri.pdf"   # 3x

# Fase 3 — os casos ruins (venv do tronco)
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\casos_ruins.py classica
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\casos_ruins.py foco
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\sobreposicao.py
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\estados.py classica
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\titulo_longo.py
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\sonda.py tudo
#   alvos de sonda.py: tipografia | controles | enfases | refluxo | vazio | dica | menus
```

Artefatos da crítica em `benchmarks\reports\critique\ui\`: 10 capturas `c1_*_1024x768_*.png`
(o tamanho recusado), `c1_titulo_longo_1920.png` + `z_titulo_longo_barra.png` (a sobreposição),
`c1_estados_{claro,escuro}_foco{0,1,2}.png` (a prancha que faltava) e os recortes ampliados
`z_botoes_*`, `z_marcas_*`, `z_foco_*`.

---

## §9 — Veredito

**REPROVADO.**

O piso funcional foi levantado e eu confirmo cinco dos seis portões com medição própria. A
fronteira `ui/` × `qt/` é real, o checador de contraste é engenharia de verdade, a paleta
escura é projetada e a disciplina de cor é de ferramenta profissional. Nada disso é pouco.

Mas a pergunta da carta §1 é se um enxadrista profissional trocaria a ferramenta dele por esta,
e a resposta é não, por três razões que nenhum portão desta frente mediu:

- **Ela não cabe na tela dele.** Recusa 1366×768; 13 % a 37 % dos controles de cada aba ficam
  abaixo da borda inferior, incluindo a ação primária da Revisão e do Dataset.
- **Ela não tem hierarquia.** Duas combinações tipográficas em 104 widgets, três primários
  simultâneos, 40 botões de peso idêntico numa aba, e o elemento mais destacado da tela
  principal é uma lista vazia com anel de foco.
- **Ela quebra com uma entrada comum.** Um nome de arquivo que já está na pasta `PDF/` do
  projeto desenha dois botões um sobre o outro e joga o rótulo para fora da janela de 1920 px.

E a medição tem dois problemas de honestidade que precisam ser corrigidos antes do ciclo 2: a
pilha publicada para o pior travamento **não é a que o instrumento devolve**, e a mediana de
três execuções **esconde um congelamento de 1,3 segundo** que o usuário vive toda vez que abre
o programa.

O caminho está aberto e é curto: os itens 1 a 8 do §7 são consertos localizados com alvo
numérico, e os itens 9 a 18 são a diferença entre passar no WCAG e parecer uma ferramenta.
