# F9 — Interface, crítica do ciclo 7

```
VEREDITO: REPROVADO
CICLO: 7
FRENTE: F9 (Interface)
```

**Reprova por uma coisa só, e é a segunda das duas que o ciclo 5 pôs como condição de aprovação.**
A primeira — a cor da dica do campo — está **fechada de verdade**, e eu a ataquei em quatro estados
que o teste do construtor não amostra, com o pixel, nas duas peles: ela não cai em nenhum. A
segunda — o estado vazio da aba principal mandando apertar um botão que existe — **não fechou**, e
hoje ela está **pior** do que quando o ciclo 5 a mediu.

---

## Nota de procedimento

Rodei os nove portões do placard, do zero, com `--saida` sempre apontando para
`benchmarks\reports\critique\ui\c7\`. **Conferi o destino de cada script antes de rodá-lo**; os
instrumentos do crítico do ciclo 5 (`c5_vazios.py`, `c5_regioes.py`) e o `c6_rodape.py` do
construtor não gravam arquivo nenhum, e os módulos do arnês receberam `--saida` em toda invocação.
Nada foi escrito fora de `docs\quality\F9_CRITIQUE_C7.md` e da minha pasta.

Abri **as 36 capturas**. Onze instrumentos novos meus, todos em
`benchmarks\reports\critique\ui\c7\`, nenhum grava fora dela:

| instrumento | o que responde |
|---|---|
| `c7_vazio_na_tela.py` | o nome citado num estado vazio está **desenhado**? (a régua do c6 aceita dica) |
| `c7_fonte_da_captura.py` | as 36 foram mesmo desenhadas em Segoe UI? (contra o pixel, não contra o manifesto) |
| `c7_dica_nos_estados.py` | a dica do campo em **4 estados** × 3 widgets × 2 peles |
| `c7_icones_da_janela.py` | o item 4 na **janela inteira**, e não só na barra do visor |
| `c7_barra_indeterminada.py` | a barra do rodapé anda ou enche? |
| `c7_rodape_estados.py` / `c7_rodape_elisao.py` | o rodapé em 5 estados, e quanto ele elide com quanto espaço livre |
| `c7_rotulos_repetidos.py` | dois controles visíveis com o mesmo rótulo e estados diferentes |
| `c7_janela_pequena.py` | 1024×768, 900×700, 800×600 e a FEN longa em toda largura |
| `c7_tabuleiro_estudo.py` | o tabuleiro da aba Estudo (que nenhum ciclo mediu) |
| `c7_estados_do_botao.py` | repouso × foco × pressionado × desabilitado |
| `sab_c7/` | **oito formas novas** de operação de fundo contra o detector já alargado |

**Três vezes o meu olho errou e a régua acertou**, e registro as três porque elas são a razão de a
carta §3.1 mandar medir: (a) achei que as setas `◀ anterior` apontavam para o lado errado — não
apontam, o glifo é que desaparece; (b) achei que o tabuleiro da aba Estudo não era quadrado — é,
585×585; (c) achei que os dois campos empilhados do grupo Filtros tinham bordas direitas
diferentes — a linha que amostrei era a moldura do grupo, e eu não tenho a medida, então **não
afirmo o defeito**.

---

## §1 — Comparação às cegas (substituição do §2.1)

A ordem de serviço mantém a substituição das rodadas anteriores: em vez de amostras rotuladas, os
**nove critérios de desenho**, cada um com a pergunta *"isto sobrevive ao lado do Affinity
Publisher, do Chessbase 17 e do Scrivener?"* e com a medida que sustenta a resposta.

### 1. Hierarquia visual — **NÃO SOBREVIVE, e piorou neste ciclo**

Continua verdadeiro o que o ciclo 5 mediu: **6 de 6 abas sem ação primária própria**; a única
primária da janela é `OCR melhor diagrama`, e ela mora na barra do **visor**, do outro lado do
divisor. Na Revisão, `Corrigir agora`, `Marcar revisado`, `Pular`, `Reabrir` e `Próximo pendente`
saem com a mesma face.

**O que piorou é o par de nomes.** O estado vazio da aba Resultado — a aba que abre — manda usar
`"OCR todos diagramas"`. Na pele **clássica**, que é a padrão (`ui/pele.py:163`, o fallback e a
primeira da lista), esse nome é desenhado por **zero** controles visíveis, nas três larguras. O
que o olho encontra a 40 px de distância, em azul, é **`OCR melhor diagrama`** — outro comando
(`ler_melhor`, *"Ler o melhor diagrama da página"*, contra `ler_pagina`, *"Ler esta página"*).
A frase não deixa de orientar: ela orienta **para o botão errado**.

Medido (`c7_vazio_na_tela.py`, união do que as seis abas mostram, duas peles × três larguras):

```
  classica 1920x1080  citado='OCR todos diagramas'  DESENHADO=NAO  decoy_na_tela=['OCR melhor diagrama']
  classica 1366x768   citado='OCR todos diagramas'  DESENHADO=NAO  decoy_na_tela=['OCR melhor diagrama']
  classica 1280x800   citado='OCR todos diagramas'  DESENHADO=NAO  decoy_na_tela=['OCR melhor diagrama']
  foco     (3 tamanhos)                             DESENHADO=sim
```

Affinity Publisher não imprime uma frase mandando apertar um botão cujo nome não está na tela, com
um botão de nome quase igual e função diferente ao lado.

### 2. Ritmo espacial — **SOBREVIVE COM RESSALVA**

A barra do visor continua em duas filas sem refluxo de 1243 a 1920. A ressalva é a aba Estudo:
**29 botões no topo, 4 filas a 1920 e 5 a 1366 e a 1280**, nas duas peles, e o refluxo produz uma
fila que carrega **um único controle** (`c6_aberto.py`, reproduzido por mim):

```
  1920: [(12, 8), (42, 10), (72, 4), (108, 7)]
  1366: [(12, 7), (42, 1), (72, 10), (102, 4), (132, 7)]   <- a segunda fila tem 1 controle
```

Uma fila de 1354 px de largura ocupada por uma caixa de marcação de 150 px é ritmo quebrado, e é o
que a captura `c6_escuro_1366x768_estudo.png` mostra a olho nu. O alvo do ciclo 3 (≤ 12 botões em
≤ 2 filas) continua reprovando por 2,4×.

Um detalhe menor, medido: o tabuleiro da Estudo é **585×585** a 1920, e 585/8 = **73,125 px** por
casa — as casas não fecham num número inteiro. Um editor de xadrez de padrão AAA escolhe 584 ou
592.

### 3. Alinhamento — **NÃO SOBREVIVE, por um par de setas**

Os nove ícones declarados da barra do visor estão numa grade só: **16×16 em 9 de 9, amplitude
0 px**. Isso é conquista do ciclo 6 e eu a confirmo.

Mas a varredura que produziu esse número lê **`j.pdf`**, o painel do visualizador, e mais nada
(`benchmarks/reports/ui/c6/c6_icones.py`, `for b in j.pdf.findChildren(...)`). Na janela inteira,
seis abas, pele clássica (`c7_icones_da_janela.py`):

```
  GLIFOS DE TEXTO fazendo papel de icone: 11
      [Resultado] Diagrama anterior     texto='◀'   caixa de tinta 5x3 px    em botao de 29x26
      [Resultado] Próximo diagrama      texto='▶'   caixa de tinta 6x6 px    em botao de 29x26
      [Resultado] (largar a peça)       texto='✕'   caixa de tinta 7x7 px    em botao de 72x25
      [Estudo]    Início da linha       texto='|◀'  caixa de tinta 8x12 px
      [Estudo]    Lance anterior        texto='◀'   caixa de tinta 5x3 px
      [Estudo]    Próximo lance         texto='▶'   caixa de tinta 6x6 px
      [Estudo]    Fim da linha          texto='▶|'  caixa de tinta 9x12 px
      [Dataset]   Página anterior       texto='<'   caixa de tinta 6x6 px
      [Dataset]   Próxima página        texto='>'   caixa de tinta 6x6 px
      [Galeria]   Primeiro diagrama     texto='|◀'  caixa de tinta 8x12 px
      [Galeria]   Último diagrama       texto='▶|'  caixa de tinta 9x12 px
```

**`◀` rende 5×3 px de tinta = 15 px²; `▶`, ao lado dele, rende 6×6 = 36 px².** O par que deveria
ser um espelho difere em **2,4× de massa**, e ampliado a 10× em
`z_est_setas_escuro.png` o `◀` não tem ápice nenhum: é um **traço horizontal chato**, enquanto o
`▶` é um triângulo sólido bem formado. Segoe UI cobre um dos dois e degenera o outro.

O efeito na tela: em três painéis (Resultado, Estudo, Galeria) **os botões de "voltar" não têm
direção legível**. Este é literalmente o defeito do §9.4 do ciclo 5 — *"um 'ícone' de 4×5 px num
botão de 26 px"* — consertado no visor e intocado nos outros quatro lugares.

### 4. Densidade × vazio — **NÃO SOBREVIVE a 1920, sobrevive abaixo**

`c5_regioes.py` e `c5_vazios.py` do crítico do ciclo 5, sem uma linha alterada, sobre as 36 novas.
Reproduzo os números do construtor **à decimal**:

| painel (1920) | claro | escuro |
|---|---|---|
| Texto | **421,8 kpx** (1044×404) | 405,1 |
| Revisão | **391,0** (1040×376) | 357,8 |
| Dataset | **367,5** (1044×352) | 350,8 |
| Estudo | 270,9 | 257,9 |
| Galeria | 222,9 | 207,0 |
| Resultado | 115,8 | 132,9 |

**10 de 12 acima de 200 kpx a 1920; 0 de 12 a 1366 e 0 de 12 a 1280** (24 capturas conferidas). É
o único critério que o construtor declara aberto sem atenuar, e a declaração está certa.

Item 7, com a régua do crítico e sem alterá-la: **ocupação 73,6 % contra o painel** (era 59,4 % no
ciclo 5), vão tabuleiro→paleta **16 px**, e **159×690 = 109,7 kpx a 0,00 % de tinta à direita da
paleta**. A ocupação subiu de verdade; o poço morto encolheu 31 % e continua lá. Os dois lados
publicados pelo construtor conferem com a minha medição.

### 5. Cor como sinal — **SOBREVIVE. Continua o melhor item da frente.**

Censo de matiz meu, restrito ao cromo (painel esquerdo, sem o visor), saturação > 0,25:

| captura | % do cromo em cor | famílias |
|---|---|---|
| `c6_claro_1920x1080_galeria` | **0,06 %** | **210° apenas** |
| `c6_escuro_1920x1080_galeria` | 0,06 % | 210° (+225° residual) |
| `c6_claro_1920x1080_revisao` | 0,08 % | **210° apenas** |
| `c6_escuro_1920x1080_revisao` | 0,08 % | 210° (+225°) |

Um matiz, menos de um décimo de por cento da superfície, idêntico entre as peles e entre os
ciclos. O vermelho aparece **só** nos dois destrutivos, e o azul **só** no primário e no foco.
Isto está no nível do Affinity.

### 6. Tipografia da interface — **SOBREVIVE, e agora a prova é do pixel**

**Confirmei o item 5 sem acreditar no manifesto.** Medi a largura de tinta de duas frases nas
capturas e comparei com o `horizontalAdvance` das duas famílias candidatas
(`c7_fonte_da_captura.py`):

```
  c6_claro_1920x1080_revisao.png   tinta na captura: 510 px (97 chars)
    Segoe UI  advance= 510.00 px   erro  +0.00 %
    Alef      advance= 524.00 px   erro  +2.75 %
  c6_claro_1920x1080_resultado.png tinta na captura: 651 px (118 chars)
    Segoe UI  advance= 653.00 px   erro  +0.31 %
    Alef      advance= 669.00 px   erro  +2.76 %
```

**As 36 foram desenhadas em Segoe UI.** Três ciclos mediram tipo na fonte errada; este não. Item 5
**FECHADO**, verificado por mim e não pelo carimbo.

O censo do construtor na fonte certa (pior combinação única **64,5 %**, alvo ≤ 80 %) e a ressalva
que ele mantém contra si — peso 600 rende **+5,4 % a +13,6 %** de tinta em Segoe UI, contra
+27 %–+37 % em Alef — são honestos e batem com o que o ciclo 5 publicou.

Duas ressalvas minhas, medidas:

* **Aspas retas onde deveriam ser tipográficas** (carta §3.3, bloco Tipografia). As três mensagens
  de estado vazio usam `"` reto:
  `'Use "Ler folha" para transcrever… ou "Achar no texto…" para procurar…'`,
  `'Nenhuma folha lida. Use "Ler folha"…'`, `'…ou use "OCR todos diagramas" para ler a página
  inteira.'` Está na tela em 12 das 36 capturas.
* **Inglês no meio do português**, na coluna de headers da Galeria: `Limpar os headers`,
  `Copiar headers para todos`, e o rótulo `outro` em minúscula entre `White`, `Black`, `Event`,
  `Site`, `Date`, `Round`, `Result`, `Annotator` — oito tags PGN capitalizadas e uma palavra
  portuguesa em caixa baixa na mesma coluna.

### 7. Controles — **SOBREVIVE, com duas ressalvas medidas**

Repouso × pressionado × desabilitado, no pixel, nas duas peles (`c7_estados_do_botao.py`):
**97,6 %** dos pixels mudam no pressionado (ΔRGB máx 196) e **98,9 %** no desabilitado (ΔRGB máx
229). O foco eu conferi na captura publicada, e não no arnês: `Negrito` na
`c6_claro_1920x1080_texto.png` tem **168 pixels azuis** de moldura contra **0** no `Itálico` ao
lado. **O anel de foco existe e é visível.**

Ressalva A — **os 11 glifos de texto do critério 3**.

Ressalva B — **dois controles visíveis com o mesmo rótulo e estados diferentes**
(`c7_rotulos_repetidos.py`, 1920, seis abas, duas peles):

```
  [Galeria]   'Cancelar'               2x  habilitados=1 desabilitados=1   <<< ESTADOS DIFERENTES
  [Galeria]   'Varrer o livro'         2x  habilitados=2
  [Resultado] 'Aplicar a FEN digitada' 2x  habilitados=1 desabilitados=1   <<< (pele foco)
  [Resultado] 'Salvar a posição'       2x  habilitados=1 desabilitados=1   <<< (pele foco)
```

Na Galeria há **dois botões "Cancelar" na tela ao mesmo tempo**, um vivo e um cinza: o de cima
cancela a varredura do livro, o do rodapé cancela a leitura do dataset, e nada na tela diz qual é
qual. A duplicação das pílulas que o ciclo 5 nomeou continua — e agora com os **estados
divergindo**, o que é pior do que a duplicação simples: o usuário lê o botão cinza do painel e
conclui que a ação não está disponível enquanto a pílula acima dela está viva.

### 8. Estados vazios — **NÃO SOBREVIVE, pela mesma frase pela terceira vez**

Dois dos três fecharam e eu confirmo: `'Ler folha'` e `'Achar no texto…'` são **desenhados** por
controles visíveis nas duas peles e nas três larguras. A caixa de legenda da Galeria ganhou
`placeholderText` — *"A legenda impressa do diagrama aparece aqui depois da varredura."* —, o que
fecha metade do §9.10 do ciclo 5.

O terceiro é o bloqueante, e está no §3 abaixo.

Uma ressalva à parte, do mesmo feitio: na coluna "Cabeçalhos do PGN" há **dois campos idênticos
empilhados sob a palavra `outro`**, sem nada dizendo que o de cima é o nome e o de baixo o valor.
Eles têm `accessibleName` — `"Nome do header extra"` e `"Valor do header extra"` — e o comentário
do código diz, com todas as letras, que a dupla é *"clara para quem vê a coluna e muda para quem
ouve o campo"*. Medido na captura, é o contrário: **quem ouve recebe a distinção e quem vê não.**

### 9. A pele escura — **SOBREVIVE**

Projetada e não invertida: contraste **296 pares / 218 sob portão / 0 reprovados** nas duas peles,
com a mesma menor folga (3,27:1 e 3,03:1) nos dois. Listras de tabela próprias, `pressionado` que
escurece, superfície elevada própria.

As duas ressalvas antigas continuam, e eu as remedi: o tabuleiro da pele Foco é **658 px** contra
**690 px** da clássica a 1920 (**−9,1 % de área**) e **385** contra **407** a 1366 (**−10,5 %**);
a fila de pílulas do topo é quem paga.

---

## §2 — Os portões, remedidos (carta §6)

Tudo abaixo saiu de comando meu, nesta sessão, três execuções onde a carta pede três.

| portão | placard do construtor | minha medição | veredito |
|---|---|---|---|
| Contraste WCAG AA | 296 / 218 / **0**, duas peles | **296 / 218 / 0**; menor folga 3,27:1 e 3,03:1 | **CONFIRMADO** |
| Teclado + nome + papel | 216 focáveis, 0 sem nome/papel | 24+52+30+39+21+50 = **216**, seis abas `PASSOU` | **CONFIRMADO** |
| Progresso | 8 indicadores, 13 operações, **0 invisíveis** | idêntico | **CONFIRMADO no número; a régua tem furo, §4.2 e §4.3** |
| Nada bloqueia > 16 ms | **REPROVOU (6–7 ops)**, 1,1–2,0 % desta frente | **REPROVOU, 7 ops nas 3 execuções**. Medianas de 3: abrir PDF **181,3 ms**, p.41 **81,2**, p.121 **80,3**, p.42 **79,7**, rasterizar **58,0**, aba Galeria **17,2**, aba Dataset **15,5** (pior **74,5**) | **CONFIRMADO como reprovação; a ATRIBUIÇÃO é REFUTADA — §4.4** |
| fps ≥ 55 @ p95 | 99,0 · 101,4 · 107,6 → 101,4 | **102,8 · 108,6 · 104,4 → mediana 104,4**; pan 745,8–759,4; zoom 72,0–75,9 | **PASSA (90 % de folga)** |
| Sobreposição / fora | 1066×735, 0 fora | `minimumSize` **1066×735**; **0 fora** em 1024×768, 900×700 e 800×600 | **CONFIRMADO, com a leitura do §4.9** |
| Rodapé (barra × Cancelar) | 8 ociosas / 28 ocupadas / **0 contradições** | **8 / 28 / 0**; face do Cancelar separada nas duas peles | **CONFIRMADO** |
| Sabotagem do ciclo 5 (item 3) | 6 de 6 | **6 de 6**, na cópia do crítico, sem tocá-la | **CONFIRMADO** |
| Fonte das capturas (item 5) | `QFontInfo` = Segoe UI | **Segoe UI no pixel**: 510 medidos contra 510,00 de advance (Alef +2,75 %) | **CONFIRMADO por medida independente** |
| Vazio de painel (item 6) | 10 de 12 > 200 kpx a 1920 | **idêntico à decimal**; 0 de 12 a 1366 e a 1280 | **CONFIRMADO** |
| Ocupação (item 7) | 73,6 % / 16 px / 109,7 kpx | **idêntico** | **CONFIRMADO** |
| Itens 8, 10, 11 | 17/25/25, duas frases, 29 botões | **idêntico** | **CONFIRMADO** |
| Suíte nossa | 2989 passed, 1 skipped, 0 failed | **2996 passed, 1 skipped, 0 failed** em 724 s | **CONFIRMADO** (7 casos a mais que o relatado; **0 reprovados** nos dois) |
| Suíte do tronco | 4447 passed, 3 failed | **3 failed, 4447 passed, 2 skipped, 4382 subtests** em 302,65 s | **CONFIRMADO campo a campo** |

**Sobre as três reprovações do tronco**, que o relatório diz acusarem só `biblioteca.py` e
`substituicao.py`: elas acusam **seis** entradas, e a terceira é `tokens.py: 'SELECAO'`, que o
relatório não cita. Conferi: `SELECAO = "SELECAO"` entrou em `ui/tokens.py` em **2026-08-17**
(`git log -S`), muito antes desta frente. As outras acusadas — `cortina.py`, `selecao_de_area.py`,
`desenho_de_diagrama.py`, `pdf_substituicao.py` — também são pré-existentes. **A conclusão do
construtor está certa; a enumeração estava incompleta.**

---

## §3 — Defeito bloqueante

### 1. O estado vazio da aba que abre manda apertar um botão que a pele padrão não desenha — e há um botão de nome quase igual, com outra função, ao lado

**Onde.** `chess_diagram_ocr/qt/painel_de_resultado.py:87`, `MENSAGEM_VAZIA`. Visível em
`c6_claro_1920x1080_resultado.png`, `c6_claro_1366x768_resultado.png` e
`c6_claro_1280x800_resultado.png` — e em toda sessão que abra na pele padrão sem diagrama aberto,
que é o primeiro estado que o produto mostra.

**O que.** A frase é:

> Nenhum diagrama aberto. Clique num diagrama marcado da página, ou use **"OCR todos diagramas"**
> para ler a página inteira.

Na pele **clássica** — que é a padrão: `ui/pele.py:163` devolve `CLASSICA` para nome inválido e é
a primeira de `PELES` — o texto `OCR todos diagramas` é desenhado por **zero** controles visíveis,
nas três larguras. O comando que a frase quer (`ler_pagina`) está na barra do visor como um botão
**só de ícone**, sem texto. O nome só existe na **dica** desse botão.

O que está desenhado, em azul, 40 px à direita, é **`OCR melhor diagrama`** — o `rotulo_curto` de
`ler_melhor`, *"Ler o melhor diagrama da página"*. **É outro comando**: lê um diagrama, não a
página. A frase manda o usuário para o controle errado, e o controle errado é o mais visível da
barra.

**Como reproduzir.**

```bat
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe ^
    benchmarks\reports\critique\ui\c7\c7_vazio_na_tela.py
```

```
  classica 1920x1080  citado='OCR todos diagramas'  DESENHADO=NAO  regua_do_c6=passa  decoy_na_tela=['OCR melhor diagrama']
  classica 1366x768   citado='OCR todos diagramas'  DESENHADO=NAO  regua_do_c6=passa  decoy_na_tela=['OCR melhor diagrama']
  classica 1280x800   citado='OCR todos diagramas'  DESENHADO=NAO  regua_do_c6=passa  decoy_na_tela=['OCR melhor diagrama']
```

Ou, sem rodar nada: abra `c6_claro_1920x1080_resultado.png` e leia a barra do visor. Recorte
ampliado em `benchmarks\reports\critique\ui\c7\z_barra_resultado_claro.png` e
`z_vazio_resultado_claro.png`.

**Por que reprova.**

1. **É a mesma frase pela terceira vez.** O ciclo 5 mediu *"Ler página"* com 0 controles. O
   primeiro conserto do ciclo 6 trocou o literal por `rotulo("ler_pagina")` = *"Ler esta página"*
   e produziu **0 controles**. O segundo conserto trocou para `rotulo_de_botao("ler_pagina")` =
   *"OCR todos diagramas"* e produz **0 controles na pele padrão**. O construtor achou o segundo
   estado *olhando* e o registrou com honestidade exemplar; o terceiro estado ele não achou porque
   escreveu um portão que o aprova.

2. **Está pior do que estava.** Em ciclo 5 o nome não batia com nada, e o usuário sabia que tinha
   de procurar. Hoje ele bate quase com um botão em destaque que faz **outra coisa**. Carta §3.3,
   bloco Funcional: *"Mensagem de erro que não diz o que fazer a seguir"* e *"Estado vazio sem
   orientação"* — a orientação existe e está errada, que é a forma cara do defeito.

3. **É o sétimo instrumento cego desta frente, e o segundo escrito neste ciclo.** A guarda
   `tests/test_qt_janela.EstadoVazioNaTelaTests._lido_na_tela` monta o conjunto do "que se lê na
   tela" assim:

   ```python
   dica = (controle.toolTip() or "").strip()
   if dica:
       nomes.add(dica.splitlines()[0].split(" — ")[0].strip())
   ```

   O conserto do mesmo ciclo pôs `"OCR todos diagramas — Ler esta página"` na dica do botão
   só-de-ícone. A dica alimenta o portão; o portão fica verde. **Uma dica não está na tela**: ela
   exige que o ponteiro pouse sobre o ícone certo, e o usuário que lê a frase não sabe qual é o
   ícone certo — é justamente isso que a frase deveria dizer. O portão escrito para fechar
   *"um instrumento afirma o que a tela não contém"* afirma o que a tela não contém.

4. **É a condição que o ciclo 5 pôs, com todas as letras:** *"Feito isso, e feito o item 2 do §9
   (…), aprovo"*. O item 1 está fechado. O item 2 não está.

**O conserto é uma linha, e há duas formas de fazê-lo:**

* dar ao botão de `ler_pagina` na pele clássica o `rotulo_curto` como **texto visível** (é o que a
  pele Foco já faz, e lá a frase fecha); **ou**
* fazer a `MENSAGEM_VAZIA` citar o nome que a pele **corrente** desenha, resolvendo o rótulo pela
  pele em vez de pelo catálogo.

**E o portão tem de mudar junto**: `_lido_na_tela` não pode aceitar `toolTip()`. Se ele aceitar, o
próximo conserto que mover o nome para uma dica passa de novo. *Alvo, cobrado por teste: para cada
nome entre aspas nas três mensagens de estado vazio, existe um controle **visível** cujo `text()`
— e só o `text()` — é esse nome, em **cada** pele, nas três larguras; e a prova de vida remove o
texto do botão e exige que o portão reprove.*

---

## §4 — Defeitos não bloqueantes

Em ordem de custo, com a medida de cada um.

### 4.1 O rodapé elide 39 de 62 caracteres com 1534 px livres na mesma faixa

Carta §3.3, **primeiro item**: *"Qualquer texto cortado, sobreposto ou com reticências onde
caberia"*. Medido em `c7_rodape_elisao.py`, nas três larguras:

```
=== janela 1920 px, faixa do rodape 1920 px ===
  QLabel         dado= 1500 px  tinta=  98 px  inteiro pede  98 px
  QLabel         dado=  162 px  tinta= 162 px  inteiro pede 162 px
  RotuloElidido  dado=  130 px  tinta= 126 px  inteiro pede 313 px  ELIDE
        inteiro   = '1937 Kemeri.pdf · p. 121 de 289 · nenhum diagrama nesta página'
        desenhado = '1937 Kemeri…esta página'   (perde 39 chars)
  tinta total dos rotulos: 386 px de 1920 px -> livre 1534 px
```

Livre: **1534 px a 1920**, **980 px a 1366**, **894 px a 1280**. O que sobrevive à elisão —
`1937 Kemeri…esta página` — não é uma frase; o que morre é a **informação inteira** (a página, o
total e o resultado da detecção). Está nas **36** capturas, nas duas peles, nas três larguras.

A causa é `qt/rotulo.RotuloElidido`, e ela é um conserto legítimo do ciclo 1 (um nome de livro de
149 chars empurrava o `minimumSizeHint` da janela de 1243 para 1513 px). O que ninguém mediu foi o
outro lado: com `minimumWidth(0)` e `Preferred`, o leiaute dá **130 px** a este rótulo e **1500 px**
ao vizinho que usa 98. *Alvo: nenhum rótulo elidido enquanto houver folga não usada na mesma
faixa; cobrado por um teste que compara `texto_inteiro` com `text()` e soma a folga da barra.*

### 4.2 Barra indeterminada com o total conhecido — e o portão que existe para pegar isso é vencido por um nome de variável

Carta §3.3, bloco Funcional: *"Barra de progresso indeterminada onde o total é conhecido"*.

**A barra é indeterminada, medido no pixel das capturas** (`c7_barra_indeterminada.py`): o bloco
azul tem sempre **59 px** e a borda esquerda dele muda de captura para captura — 1713, 1721, 1737,
1743, 1757, 1759 — dando a volta na pista de 118 px (é por isso que às vezes ela aparece como dois
blocos). Bloco de comprimento fixo que anda e dá a volta é a marquise do Qt.

**O total é conhecido, e o próprio código diz que é.**
`qt/painel_do_dataset._registrar_a_leitura` (linha 425):

> *"**Indeterminada de propósito, e o número está aqui.** O total é conhecido —
> `contagem_de_amostras()` responde 5.431 sem abrir o arquivo — e mesmo assim `total=` fica em
> zero (…)"*

E o rodapé **imprime o número**: `leitura do dataset (5431 amostra(s))`, em 28 das 36 capturas.

**O portão vê `total=` e não vê o total.** `caissa.ui.audit.progresso` tem uma heurística exatamente
para este caso — `PISTAS_DE_TOTAL = ("total","count","epochs","epocas","paginas","n_","len")`
aplicada ao `detail=`. O `detail` real é `f"{quantas} amostra(s)"`, e `quantas` não casa com pista
nenhuma:

```
  detalhe='f"{quantas} amostra(s)"'   -> evidencia=''                       -> 0 defeitos
  detalhe='f"{total} amostra(s)"'     -> evidencia='a contagem esta no detail: …'  -> DEFEITO BLOQUEANTE
```

**Mesma tela, mesmo 5431, mesma barra andando: renomeie uma variável local e o portão inverte o
veredito.** É o mais consequente dos furos deste ciclo, porque o que ele esconde é um item que a
carta diz reprovar sozinho.

**E não é limitação de biblioteca.** Registrei uma operação com `total=289` na janela viva
(`c7_rodape_elisao.py`) e a barra saiu **`min=0 max=100` — DETERMINADA**. A máquina existe; falta o
argumento. O argumento do código — que `load_rows` não tem callback e a barra ficaria parada em
0 % — é uma escolha defensável de UX, mas a carta §5.2 diz que *"é uma limitação da biblioteca"*
não aprova, e o conserto correto é dar progresso ao leitor, não declarar desconhecido um total que
o código imprime na linha de baixo.

*Alvo: a heurística de "total conhecido" deixa de depender do nome da variável — passa a marcar
qualquer `detail=` que contenha uma interpolação numérica, ou o portão passa a exigir `total=`
sempre que a mesma função chame um contador. Prova de vida: renomear `quantas` para `n` e o portão
continuar acusando.*

### 4.3 O detector de thread: 7 das 8 formas novas escapam como operação

O alvo do §9.3 do ciclo 5 está batido — **6 de 6** na cópia sabotada do crítico, conferido por mim
sem tocá-la. E a sabotagem própria do ciclo 6 (8 formas, 3 furos, todos fechados) é exatamente o
método que a carta pede.

Plantei **oito formas que nenhuma das duas sabotagens anteriores tem**
(`benchmarks\reports\critique\ui\c7\sab_c7\`):

| forma | resultado |
|---|---|
| (a) `Fabrica = threading.Thread` (apelido por **atribuição**) + `Fabrica(...).start()` | **escapa** |
| (b) `functools.partial(threading.Thread, …)()` | **escapa** |
| (c) `self._pool.map(fn, itens)` (o pool nasceu no `__init__`; `map` é exclusão declarada) | **escapa** como operação |
| (d) `asyncio.to_thread(...)` | **escapa** |
| (e) `trabalhador.moveToThread(self._fio)` — o idioma canônico do Qt | **escapa** como operação |
| (f) `subprocess.Popen([...])` sem `wait` | **escapa** |
| (g) `QProcess(...).start(prog, args)` | **escapa** |
| (h) `importlib.import_module("threading").Thread(...)` | **pego** |

```
DEFEITOS BLOQUEANTES (3)
  - SabotadorC7.__init__          INVISIVEL (constroi ThreadPoolExecutor)
  - SabotadorC7.__init__          INVISIVEL (constroi QThread)
  - SabotadorC7.h_import_dinamico INVISIVEL (constroi mod.Thread)
```

**Uma das oito operações é nomeada (h). Cinco não deixam rastro nenhum (a, b, d, f, g). Duas
(c, e) só aparecem pela construção que o `__init__` faz** — e uma linha dizendo
`SabotadorC7.__init__ constroi QThread` não diz que `e_move_to_thread` é uma operação de fundo
nem que `c_map_no_pool` é outra.

**Isto é honesto sobre o tronco de hoje e não sobre o de amanhã**: varri `qt/` e `ui/` e o produto
**não usa** `moveToThread`, `.map(` num pool, `to_thread` nem apelido por atribuição. O único
acerto é `subprocess.Popen` em `ui/leitura_do_pdf.py:127,129`, que abre o PDF num visualizador
externo e não tem o que mostrar. Ou seja: **os "0 invisíveis" de hoje são verdade; o portão é que
não consegue mantê-los**, e vai passar em verde no dia em que alguém escrever o idioma de thread
mais comum do Qt. *Alvo: `moveToThread` e o apelido por atribuição entram na régua; a sabotagem C7
fica no repositório do arnês como a C5 e a C6 ficaram.*

### 4.4 "O resto é PyMuPDF" cobre 4 das 7 operações, e está errado na maior

O portão **REPROVOU nas três execuções, com 7 operações**, e isso o placard declara. O que o
placard afirma além do medido é a exculpação.

**(a) A atribuição só é impressa para as 4 primeiras.** `bloqueio.py:939` — `for linha in
relatorio["operacoes"][:4]`. As três restantes não aparecem no relatório de texto.

**(b) Na maior violação, PyMuPDF é pouco mais da metade.** `abrir PDF`, mediana **181,3 ms**,
11,3× o orçamento:

| execução | PyMuPDF | pathlib/os (disco) | builtins | qt/ (esta frente) |
|---|---|---|---|---|
| 1 | 73,7 ms — **54,9 %** | 47,7 ms — **35,5 %** | 8,1 ms | 1,9 ms — 1,4 % |
| 2 | 72,3 ms — **52,8 %** | 38,0 ms — **27,7 %** | 21,5 ms | 2,1 ms — 1,5 % |

**28 %–36 % da pior operação da janela é E/S de disco na thread da interface** — e a pilha do pior
nomeia `nt.stat <- marcas.py:77 _marca_de`. Isso é decisão desta frente, não da biblioteca.

**(c) Nas duas trocas de aba, a atribuição não mede nada.** A passada de `cProfile` reproduz
**1,05–1,41 ms** de um congelamento medido de **51,0–74,5 ms** (1,9 %) na aba Dataset, e
**0,74–1,01 ms** de 18,5–20,3 ms (4,6 %) na Galeria. Nenhuma das duas toca PyMuPDF. **O que trava a
janela por até 74,5 ms quando se clica na aba Dataset não está em perfil nenhum**, e o placard o
cobre com um número medido noutra operação.

Não bloqueio: a reprovação está declarada há três ciclos e a parte desta frente nas quatro
operações de PDF é mesmo de 1,4 % a 2,2 %, que eu confirmo. *Alvo: imprimir a atribuição das
**sete**, e explicar `aba Dataset: pior 74,5 ms` com uma medição que reproduza os 74,5 ms.*

### 4.5 A FEN continua cortada em toda largura abaixo de 1920, e o teste do ciclo 6 não consegue vê-lo

O conserto do ciclo 6 pôs o cursor em 0. Isso muda **qual ponta** some, não **se** some
(`c7_janela_pequena.py`):

| largura | campo | FEN inicial | FEN de meio-jogo (72 chars) |
|---|---|---|---|
| 1920 | 592 px | cabe | cabe |
| 1366 | 414 px | cabe | **corta 15 chars** |
| 1280 | 387 px | **corta 3** | **corta 19** |
| 1024 | 286 px | **corta 17** | **corta 33** |

A 1024 vê-se `'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQ'` — **sem reticência e sem sinal**, exatamente
o diagnóstico que o construtor escreveu para o defeito que achou. E é mais perigoso que antes:
um prefixo bem formado parece uma FEN completa; um sufixo (`…RNBQKBNR w KQkq - 0 1`) não parecia.

**A régua não pega.** `tests/test_qt_painel_de_estudo` afirma
`campo.cursorPositionAt(QPoint(4, h/2)) == 0` — e, três linhas antes, **assegura que o campo é
estreito demais** (`assertGreater(horizontalAdvance(fen), campo.width())`). O teste monta o caso
cortado e verifica só de que lado o corte cai. Ele não pode reprovar enquanto a ponta direita
estiver sumindo em silêncio. *Alvo: `cursorPositionAt` na borda **direita** devolve `len(fen)`, ou
o campo mostra reticência, em 1920, 1366, 1280 e 1024.*

### 4.6 "Motivo" ilegível em 17 de 27 linhas a 1920 e 25 de 27 a 1366 e 1280

Reproduzido sem alterar o instrumento do construtor: coluna de **694 px** a 1920 → **17 de 27**;
**382 px** a 1366 e **334 px** a 1280 → **25 de 27** nas duas. É o item 8 do §9 do ciclo 5, aberto.

A tabela é a ferramenta de trabalho da revisão, e o "Motivo" é a única coluna que diz **por quê**.
Um revisor a 1366 lê a razão de **2 dos 27** itens da fila. E há **391,0 kpx de corpo de tabela
vazio** logo abaixo (item 6): a altura para uma segunda linha existe. *Alvo: `Motivo` com quebra em
duas linhas ou painel de detalhe; 0 de 27 pedindo mais largura do que a coluna tem, nas três
larguras.*

### 4.7 O item 4 fechou na barra do visor e continua aberto nos outros quatro painéis

Já medido no critério 3: **11 glifos de texto** fazendo papel de ícone, com caixas de **5×3** a
**9×12 px**, e o par `◀`/`▶` com **2,4× de diferença de massa**. A tinta dos ícones declarados
continua em **34,0 %–53,1 %** (amplitude relativa **43,9 %** contra o alvo de ±20 %), como o
construtor declara. *Alvo do §9.4 do ciclo 5, agora com o escopo certo: caixa única (±1 px) e
tinta dentro de ±20 % em **todos** os botões só-de-ícone da **janela**, e a varredura deixa de ser
`j.pdf.findChildren` para ser `j.findChildren`.*

### 4.8 As duas frases simultâneas do Dataset, e o "Cancelar" que nunca tem o que cancelar

As duas frases confirmadas nas seis combinações: `'Lendo o dataset'` no centro do painel e
`'leitura do dataset (5431 amostra(s))'` no rodapé, ao mesmo tempo. Item 10 do §9 do ciclo 5.

E o `Cancelar` do rodapé fica **desenhado e cinza** nas 8 capturas ociosas, sem barra e sem
operação (`z_rodape_ocioso_claro.png`). O portão do rodapé mede que a **face** dos dois estados é
separada, e ela é; o que ele não pergunta é por que um botão que só serve a uma operação em curso
ocupa o canto quando não há operação. O conserto do ciclo 3 fez a **barra** sumir; o **botão**
ficou.

### 4.9 A janela não desce abaixo de 1066×735

`minimumSize` = `minimumSizeHint` = **1066×735**. Pedi 1024×768, 900×700 e 800×600: a janela
devolve **1066×768** e **1066×734**, e **0 controles ficam fora** — porque ela simplesmente não
encolhe. A carta §3.2 pede o caso 800×600; a resposta honesta é **"não existe"**: num monitor de
1024×768 a janela transborda a tela em 42 px de largura. Não bloqueia (1366×768 é o alvo declarado
e cabe), mas os três ciclos que publicaram *"1066×735, 0 fora"* publicaram metade da frase.

### 4.10 Miudezas medidas

* **Aspas retas** nas três mensagens de estado vazio (critério 6).
* **`headers` em inglês** e **`outro` em caixa baixa** entre oito tags PGN capitalizadas.
* **Dois campos idênticos sob a palavra `outro`** sem rótulo visível que os distinga (critério 8).
* **Casas de 73,125 px** no tabuleiro da Estudo a 1920 (585/8).
* **Dois destrutivos vermelhos lado a lado** na aba Estudo (`Apagar variante`, `Apagar daqui`).
* **Uma fila de 1354 px com um único controle** na Estudo a 1366 e 1280.

---

## §5 — O que este ciclo conquistou, e eu confirmo com número

Não estou dando crédito por esforço. Estou registrando o que **remedi e bateu**.

1. **O bloqueante do ciclo 5 está morto, e eu tentei matá-lo em quatro estados.** O teste do
   construtor amostra o campo habilitado. Eu medi **habilitado, desabilitado, só-leitura e com
   foco**, em três widgets com `placeholderText`, nas duas peles — **24 medições**:

   ```
   classica  Resultado QLineEdit  7.08 / 6.54 / 7.08 / 19.23
   classica  Dataset   QLineEdit  6.54 / 6.54 / 6.54 /  6.54
   classica  Galeria   QTextEdit  7.08 / 6.54 / 7.08 /  7.08
   foco      Resultado QLineEdit  7.95 / 7.14 / 7.95 / 14.69
   foco      Dataset   QLineEdit  7.14 / 7.14 / 7.14 /  7.14
   foco      Galeria   QTextEdit  7.95 / 7.14 / 7.95 /  7.95
   ```

   **Mínimo 6,54:1 contra um piso de 4,5.** O par exato que o ciclo 5 fotografou a **3,96:1** — o
   campo de busca do Dataset, habilitado — mede **6,54:1**. Nenhum estado o derruba. **Fechado.**

2. **O construtor achou, sozinho, que o próprio conserto tinha reaberto**, e disse isso em primeiro
   lugar no relatório, com a sonda que o mostra. Isso é raro e vale ser dito, mesmo tendo eu achado
   a terceira volta.

3. **As duas sabotagens do detector de thread são o método certo**, e o resultado é real: 6 de 6 na
   do ciclo 5 (conferido por mim na cópia intocada) e 8 de 8 na própria. O detector do ciclo 5
   pegava 1 de 6.

4. **As 36 capturas estão na fonte do produto, e a prova é do pixel** — não do carimbo. Três ciclos
   julgaram tipografia em Alef. Este não.

5. **A ocupação subiu de verdade**: 59,4 % → **73,6 %** contra o painel, com o vão de 203 px → 16 px
   sustentado. E o construtor publicou os **dois** lados — a ocupação que subiu e os 109,7 kpx que
   sobraram —, recusando o número mais bonito.

6. **Nada foi afrouxado.** A suíte nossa passa **2996** com **0 reprovados**; a do tronco fecha
   campo a campo com o relatado, com as três reprovações de sempre, todas pré-existentes,
   verificadas por `git log -S`.

7. **A disciplina de caminho de saída foi respeitada**: os quatro instrumentos de caminho cravado
   não foram rodados, e as sabotagens gravaram em pasta temporária. Depois de duas rodadas de
   capturas destruídas, este ciclo não perdeu nenhuma.

---

## §6 — O que especificamente precisa mudar para eu aprovar

**Um item bloqueia. Só ele.**

1. **Faça o nome que o estado vazio cita aparecer na tela, e feche o portão que o deixou passar.**
   Duas metades, as duas obrigatórias:
   - **Produto**: na pele **clássica**, ou o botão de `ler_pagina` mostra `rotulo_curto`
     (`"OCR todos diagramas"`) como **texto**, ou `painel_de_resultado.MENSAGEM_VAZIA` passa a citar
     o nome que a **pele corrente** desenha. Hoje a frase cita um nome que a pele padrão não escreve
     em lugar nenhum, com `OCR melhor diagrama` — **outro comando** — em destaque ao lado.
   - **Portão**: `tests/test_qt_janela.EstadoVazioNaTelaTests._lido_na_tela` **deixa de aceitar
     `toolTip()`**. Uma dica não é a tela.

   *Alvo, cobrado por teste: para cada nome entre aspas nas três mensagens de estado vazio existe
   um controle **visível** cujo `text()` é esse nome, em **cada pele**, a 1920, 1366 e 1280 —
   `c7_vazio_na_tela.py` devolvendo `DESENHADO=sim` nas 18 linhas. Prova de vida: apagar o texto do
   botão faz o portão reprovar; hoje ele passa.*

**Não bloqueiam, e entram no §9 da próxima ordem de serviço nesta ordem:**

2. **O rodapé elide 39 de 62 chars com 894–1534 px livres.** Dê ao `RotuloElidido` a folga que a
   faixa tem antes de cortar. *Alvo: 0 rótulos elididos enquanto houver folga não usada na mesma
   barra, cobrado comparando `texto_inteiro` com `text()`.*
3. **Passe `total=` na leitura do dataset**, ou pare de imprimir 5431 ao lado de uma marquise. E
   **conserte a heurística de "total conhecido"**, que hoje depende de a variável se chamar `total`.
   *Alvo: renomear `quantas` para `n` não muda o veredito do portão; e a barra vira determinada.*
4. **Imprima a atribuição das sete operações do portão de bloqueio**, não das quatro primeiras, e
   explique `aba Dataset: pior 74,5 ms` com uma medição que reproduza os 74,5 ms. **Pare de dizer
   "o resto é PyMuPDF"**: em `abrir PDF` PyMuPDF é 52,8 %–54,9 % e o disco é 27,7 %–35,5 %.
5. **`Motivo` legível**: 0 de 27 linhas pedindo mais largura do que a coluna tem, nas três
   larguras. Há 391,0 kpx de tabela vazia logo abaixo.
6. **Item 4 com o escopo certo**: `j.findChildren` no lugar de `j.pdf.findChildren`; caixa única
   (±1 px) e tinta em ±20 % nos **11** glifos de texto também. Comece pelo `◀`, que rende 5×3 px de
   tinta contra 6×6 do `▶` ao lado.
7. **A FEN não pode sumir em silêncio em nenhuma largura.** *Alvo: `cursorPositionAt` na borda
   direita devolve `len(fen)`, ou há reticência, a 1920, 1366, 1280 e 1024.*
8. **Item 6 continua aberto**: 10 de 12 painéis acima de 200 kpx a 1920.
9. **Item 7 continua parcial**: 109,7 kpx de tinta zero à direita da paleta.
10. **Alargue o detector de thread** para `moveToThread` e para o apelido por atribuição, e guarde
    a sabotagem C7 ao lado da C5 e da C6.
11. **Um rótulo, um controle**: dois `Cancelar` visíveis com estados diferentes na Galeria; duas
    pílulas duplicando botões com estados divergentes no Resultado da pele Foco.
12. **Aspas tipográficas** nas três mensagens de estado vazio; `headers` em português; rótulo
    visível para os dois campos empilhados sob `outro`.

---

## §7 — Como reproduzir

```bat
:: portoes -- --saida SEMPRE para a pasta do critico
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m caissa.ui.audit.contraste --saida benchmarks\reports\critique\ui\c7
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --saida benchmarks\reports\critique\ui\c7
sh benchmarks\reports\critique\ui\c7\c7_portoes.sh    :: bloqueio x3, quadros x3, teclado
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly   :: no tronco

:: sabotagens (nenhuma escreve sobre o tronco nem sobre as capturas)
.venv\Scripts\python.exe -m caissa.ui.audit.progresso ^
    --tronco benchmarks\reports\critique\ui\c5\sabotado --saida ...\c7\tmp_sab   :: 6 de 6
.venv\Scripts\python.exe -m caissa.ui.audit.progresso ^
    --tronco benchmarks\reports\critique\ui\c7\sab_c7  --saida ...\c7\tmp_sab   :: 3 de 8

:: instrumentos deste ciclo (benchmarks\reports\critique\ui\c7\ -- nenhum grava fora dela)
c7_vazio_na_tela.py       :: 'OCR todos diagramas' DESENHADO=NAO em 3 de 3 larguras da pele padrao
c7_fonte_da_captura.py    :: Segoe UI +0.00 % / +0.31 %; Alef +2.75 %
c7_dica_nos_estados.py    :: 24 medicoes, minimo 6.54:1
c7_icones_da_janela.py    :: 11 glifos de texto; caixas 5x3 a 9x12
c7_barra_indeterminada.py :: bloco de 59 px que anda -> marquise
c7_rodape_estados.py      :: 5 estados do rodape, inclusive DUAS e TRES operacoes
c7_rodape_elisao.py       :: 130 px dados, 313 px pedidos, 1534 px livres; total=289 -> DETERMINADA
c7_rotulos_repetidos.py   :: 'Cancelar' 2x com estados diferentes
c7_janela_pequena.py      :: minimumSize 1066x735; FEN corta 3 a 33 chars
c7_tabuleiro_estudo.py    :: 585x585, quadrado, casa 73.125 px
c7_estados_do_botao.py    :: pressionado 97.6 %, desabilitado 98.9 %
c7_cor_e_bordas.py        :: 0.06-0.08 % do cromo em cor, familia 210
c7_zoom.py <png> x0 y0 x1 y1 [fator] [nome]  :: os recortes z_*.png

:: instrumentos anteriores, rodados sem alteracao (conferido que nao gravam)
critique\ui\c5\c5_vazios.py  <png..>   :: 10 de 12 acima de 200 kpx a 1920
critique\ui\c5\c5_regioes.py <png..>   :: 73,6 %, vao 16 px, 109,7 kpx
ui\c6\c6_rodape.py <png..>             :: 8 ociosas / 28 ocupadas / 0 contradicoes
ui\c6\c6_aberto.py                     :: 17/25/25, duas frases, 29 botoes em 4-5 filas
```

Artefatos meus, todos em `benchmarks\reports\critique\ui\c7\`: os doze instrumentos, a árvore
`sab_c7\`, `bloqueio_run{1,2,3}.txt`, `quadros_run{1,2,3}.txt`, `teclado.txt`, `tronco_run1.txt`,
`suite_nossa.txt`, `c7_icones.txt`, os JSON dos portões e os recortes ampliados `z_*.png`.
**Nada fora desta pasta e deste documento foi escrito por mim.**

---

## §8 — Veredito

**REPROVADO — por um defeito, e ele é uma linha de produto mais uma linha de portão.**

O bloqueante do ciclo 5 está fechado, e eu não aceitei a palavra do construtor: medi a dica do
campo em **quatro estados** que o teste dele não amostra, em três widgets, nas duas peles —
**24 medições, mínimo 6,54:1**, e o par que o ciclo 5 fotografou a 3,96:1 hoje mede 6,54:1.
Confirmei a fonte das capturas **no pixel** e não no manifesto. Confirmei **6 de 6** na sabotagem
do crítico anterior, **216** focáveis com nome e papel, **296/218/0** no contraste nas duas peles,
**104,4 fps** de mediana em três execuções, **8/28/0** no rodapé, e as duas suítes campo a campo,
com **0 reprovações** na nossa e as três de sempre — todas pré-existentes — na do tronco. E o
construtor achou, sozinho, que o próprio conserto do item 2 tinha reaberto, e o publicou em
primeiro lugar. Isso é trabalho sério.

Não aprovo porque **o estado vazio da aba que o produto abre continua mandando apertar um botão que
a pele padrão não desenha** — e, pior que no ciclo 5, agora há um botão em destaque com nome quase
igual e **função diferente** a 40 px dele. A frase deixou de não orientar e passou a orientar
errado.

E a razão de isso ter chegado ao ciclo 7 é a mesma pela sétima vez nesta frente: **um instrumento
afirmando o que a tela não contém.** Desta vez o instrumento é o portão escrito neste ciclo para
fechar exatamente este defeito, e ele passa porque aceita o texto de uma **dica** como se fosse
pixel desenhado. Encontrei mais dois do mesmo feitio — o portão de progresso que decide "o total é
conhecido" pelo **nome de uma variável local**, e o teste da FEN que **monta o caso cortado** e
verifica só de que lado o corte cai — e os dois estão no §4 como não bloqueantes.

Feito o item 1 do §6 — o botão com o nome na tela **e** o portão que deixa de aceitar dica —,
**aprovo**. Os outros onze itens são desenho, medida e disciplina de instrumento; nenhum deles
manda o usuário para o controle errado.
