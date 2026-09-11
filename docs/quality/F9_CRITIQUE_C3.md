# F9 — Crítica adversarial, ciclo 3

```
VEREDITO: REPROVADO
CICLO: 3
FRENTE: F9 (Interface)
```

---

## Nota de procedimento

Continua não havendo conjunto cego para a F9 nesta máquina. A carta §2.1 segue substituída,
como no ciclo 1, por um **julgamento itemizado dos nove critérios** (§2), cada um com a medida
que o sustenta.

**Todos os números deste documento são meus.** Rodei os seis arnesses do §6 da carta, olhei as
**36 capturas** de `benchmarks/reports/ui/c2/`, as 8 pranchas de estado, as 2 de caixa de
seleção, e produzi seis instrumentos novos em
`benchmarks\reports\critique\ui\c3\` — `atribuicao.py`, `qual_thread.py`, `quem_chama.py`,
`custo_aviso.py`, `colapso.py`, `detalhes.py`, `medidas_c3.py` — porque a Fase 3 exigia casos
que a captura feliz não tem.

**Uma correção de fato do ciclo 1 que este ciclo consertou sem alarde:** os arquivos
`*_1280x800_*` do ciclo 1 **não tinham 800 px de altura**. Os 36 do c2 têm exatamente a
dimensão que o nome anuncia — verifiquei os 36. O nome do arquivo voltou a ser verdade.

**Dezoito itens, e o placar honesto:** reproduzo **quinze** dos dezoito com número próprio.
Os três que faltam são **um item de produto** (o `csv` que voltou por uma terceira porta), **um
item de cromo** (a barra de progresso vazia permanente) e **um item de prova** (a prancha de
estados que desenha o que diz não desenhar). Nenhum dos três é grande. Os três são o motivo do
veredito, e o §7 diz exatamente o que fazer com cada um.

---

## §2 — Os nove critérios: isto sobrevive ao lado do Affinity Publisher?

Escala medida (`medir_c2.py`, `sonda.py`, janela 1920×1080, `1937 Kemeri.pdf` aberto):

| aba | neutros | primários | destrutivos | botões da aba | filas |
|---|---|---|---|---|---|
| Resultado | 22 | **1** | 1 | 9 | 3 |
| Estudo | 39 | **1** | 3 | **28** | **4** |
| Revisão | 22 | **1** | 1 | 9 | 2 |
| Texto | 25 | **1** | 1 | 12 | 3 |
| Dataset | 22 | **1** | 3 | 11 | 4 |
| Galeria | 28 | **1** | 2 | 16 | 10 |

### 1. Hierarquia visual — **AINDA NÃO SOBREVIVE, mas por outro motivo**

O defeito do ciclo 1 acabou: eram **três** botões primários simultâneos em Resultado, Estudo e
Revisão; medi **1 em cada uma das seis abas**, `excesso_de_enfase=0`. E o pior elemento do ciclo
1 — a `QListWidget` de 1059×140 vazia com anel de foco permanente, o objeto mais destacado da
aba principal — **não existe mais**: ela colapsa a zero. Isso é progresso real e eu o registro.

O que sobrou é o inverso do problema antigo. A única ênfase da janela é
**`Ler o melhor diagrama da página`, e ela está na barra do visor** — o mesmo botão nas seis
abas. Consequência medida: **6 de 6 abas não têm ação primária própria.** Na aba Revisão,
`Corrigir agora` — a ação que começa o trabalho — é hoje pixel a pixel igual a `Marcar
revisado`, `Pular`, `Reabrir` e `Próximo pendente`: **cinco retângulos cinzentos idênticos numa
fila**, e o único botão azul da tela pertence a outro painel e faz outra coisa.

O §7 do ciclo 1 pedia que as ações rebaixadas virassem neutras **"com atalho declarado"**.
Medi `ui/atalhos.por_acao` (21 ações com tecla global): `anotar_pagina`, `estudo_do_diagrama`,
`corrigir_agora` e `ler_melhor` — **quatro de cinco — não têm tecla nenhuma**; só `salvar` tem
(`Ctrl+S`). A compensação que tornaria o rebaixamento aceitável não foi entregue.

### 2. Ritmo espacial — **SOBREVIVE**

A escala de espaço continua sendo dado (`FOLGAS` com quatro valores) e o código continua a
obedecer. A ressalva do ciclo 1 — o agrupamento invisível de 4 px entre filas da barra —
**desapareceu junto com as filas**: a barra tem duas filas em toda largura e os blocos são
separados por um traço de 1 px de `qt/rotulo.separador`, que é o que o §7 pediu com essas
palavras.

Uma ressalva nova, medida (`detalhes.py`, aba Galeria a 1920): a coluna
"Cabeçalhos do PGN" empilha cinco botões e **o primeiro deles está fora do prumo dos outros
quatro**:

| botão | x da borda esquerda | largura |
|---|---|---|
| **Gravar** | **892** | **155** |
| Limpar os headers | 829 | 218 |
| Partidas da base | 829 | 218 |
| Copiar headers para todos | 829 | 218 |
| Desfazer a cópia | 829 | 218 |

**63 px de desalinho e 63 px de diferença de largura numa pilha de cinco.** É visível a olho nu
nas capturas `c2_{claro,escuro}_1366x768_galeria.png`.

### 3. Alinhamento — **SOBREVIVE. Item 15 fechado, e é limpo.**

Ciclo 1: margens esquerdas de 8, 9, 12 e 13 px conforme a aba. Medi agora, nas seis:

```
Resultado 10 px · Estudo 10 px · Revisão 10 px · Texto 10 px · Dataset 10 px · Galeria 10 px
valores distintos: [10]
```

**Um valor, seis abas, 143 controles.** A faixa de abas deixou de fazer o conteúdo pular. Isto
está fechado e não tenho ressalva.

### 4. Densidade × vazio — **NÃO SOBREVIVE, e o alvo do §7 não foi atingido**

O tapete inverteu de verdade, e o número é o do construtor (reproduzido):

| | ciclo 1 | agora (medido por mim, no pixel) |
|---|---|---|
| tapete `#312e2b`, % da janela 1920×1080 | **10,9 %** | **1,30 %** (Resultado) / 1,48 % (Estudo) |
| tabuleiro, % da mesma janela | 9,4 % | **14,64 %** / **19,02 %** |
| ocupação do canvas, Estudo | 59,6 % | **80,8 %** |
| ocupação do canvas, Resultado | 46,4 % | **58,2 %** |

Os tabuleiros são quadrados ao pixel nas nove capturas que medi (551×551, 628×628, 419×419…).
A esteira virou moldura de 12 px. Isso está certo.

**Mas o alvo do §7 era "nenhuma região de painel acima de 200 kpx com menos de 2 % de tinta", e
ele falha nas seis abas.** Varri as seis capturas claras de 1920 procurando o maior retângulo de
baixa tinta no painel esquerdo:

| aba | maior região vazia | tinta |
|---|---|---|
| Texto | **419,2 kpx** (1048×400) | **0,00 %** |
| Revisão | **394,0 kpx** (1048×376) | **0,00 %** |
| Dataset | **377,3 kpx** (1048×360) | **0,00 %** |
| Estudo | **241,4 kpx** (368×656) | **0,00 %** |
| Galeria | 217,6 kpx (800×272) | 0,00 % |
| Resultado | 211,2 kpx (1056×200) | 0,00 % |

**Sou justo com três delas:** em Texto, Dataset e Galeria o vazio é a faixa *acima* de um estado
vazio centrado, e um estado vazio centrado sempre deixa duas faixas. A métrica do ciclo 1 é, nessa
forma, insatisfazível — e eu digo isso porque foi meu antecessor que a escreveu.

**As outras três são reais:**

- **Estudo**: a caixa "Lances" é 368×656 = **241,4 kpx a 0,00 %**, com uma linha
  (`posição inicial *`) no topo. A aba onde um editor de xadrez passa o dia tem a lista de lances
  vazia, sem estado vazio, sem orientação. Não estava na lista do §7 e por isso não é cobrança —
  é o maior vazio não tratado que sobrou.
- **Revisão com a fila cheia**: o §7 nomeou "os 409,3 kpx a 0,00 % abaixo da fila". O estado vazio
  novo ("Nenhum item na fila") só aparece com **zero** itens. Com os **27 itens que a aba tem**,
  a tabela acaba em y=597 e o painel continua até y=973: **1048×376 = 394,0 kpx a 0,00 %**, contra
  409,3 kpx no ciclo 1. **Uma melhora de 3,7 %.** E a fila de ações fica presa em y=1021,
  **424 px abaixo da última linha de dado** — selecionar uma linha e clicar em `Corrigir agora`
  é uma travessia de 430 px por um campo vazio.
- **Resultado**: 1056×200 = **211,2 kpx a 0,00 %** abaixo dos controles, sem estado, sem conteúdo.

E o visor: **a página nunca se reajusta à janela.** Medi o retângulo sépia da página digitalizada
nas três larguras: **366 px de largura a 1280, a 1366 e a 1920** — idêntico ao pixel, zoom fixo em
31 %. A 1366 a página ocupa 65 % da largura útil do visor; a 1920 ela ocupa **29 % de um viewport
de 819×850**, e os outros 71 % são branco. Abrir o programa num monitor maior não dá mais página:
dá mais branco. A carta §3.2 nomeia "4K" como caso obrigatório.

### 5. Cor como sinal — **SOBREVIVE. Continua o melhor item da frente.**

Censo de matiz próprio (saturação > 0,15, passo de 15°) sobre `c2_claro_1920x1080_galeria.png`:
**quatro famílias**, e o cromo gasta **0,70 % da tela em cor**:

| matiz | % da tela | o que é |
|---|---|---|
| 210° | 0,24 % | azul: primário, foco, seleção |
| 45° | 0,18 % | o sépia da digitalização — documento |
| 0° | 0,15 % | vermelho: destrutivo |
| 240° | 0,13 % | a marca d'água da DIGAR, no PDF |

Azul = interativo, vermelho = destrutivo, e nada mais. Na pele escura o cinza do cromo é um azul
dessaturado (`#2c3036`, saturação 0,185) — é uma paleta fria deliberada, não um vazamento de
matiz. Disciplina de ferramenta profissional, mantida.

### 6. Tipografia da interface — **AINDA NÃO SOBREVIVE**

O alvo do §7 era literal — "3 tamanhos e 2 pesos presentes em cada aba" — e ele foi cumprido
literalmente. O instrumento do construtor devolve, nas **12** combinações aba × pele:
`tamanhos=[11, 12, 13] pesos=[400, 700]`. Reproduzo.

**A régua de fora conta outra história.** `sonda.py tipografia` (o censo de `QWidget.font()` do
ciclo 1), aba Galeria a 1920:

| | ciclo 1 | agora |
|---|---|---|
| widgets visíveis | 104 | **107** |
| 12 px / peso 400 / uma família | 101 (97 %) | **99 (92,5 %)** |
| widgets em `TITULO` (13 px / 700) | **0** | **3** |
| widgets em `AUXILIAR` (11 px) | 3 | 5 |
| famílias | 1 | 1 (a mono aparece em 3 das 6 abas) |

**Três widgets por aba mudaram.** Dos oito papéis que o ciclo 1 listou como idênticos — rótulo
de menu, rótulo de aba, rótulo de botão, título de grupo, cabeçalho de coluna, dado da tabela,
estado vazio, barra de status — **três** se moveram (título de grupo, cabeçalho de coluna,
título de estado vazio) e **cinco continuam iguais**.

E a escala declarada é `AUXILIAR` 8 pt / `CORPO` 9 pt / `TITULO` 10 pt = **11 / 12 / 13 px**:
dois degraus de **+9 %** e **+8 %**. O ciclo 1 escreveu, com essas palavras, *"uma diferença de
1 px em 12 (8 %) não produz hierarquia"* — e a resposta foi acrescentar um terceiro tamanho
exatamente nesse degrau. A hierarquia que de fato chega aos olhos é **o peso**, e ela chega em
2,8 % dos widgets. Nas capturas dá para ver que "Prio./Pag./Diag./Conf. min/Status/Motivo" e
"Nenhuma folha lida" estão em negrito, e isso é uma melhora verdadeira. Mas 92,5 % da janela
continua sendo uma só combinação tipográfica, e é a razão que sobra para a janela ler como demo.

### 7. Controles — **SOBREVIVE**

Item 18 fechado (`RAIO_NA_BASE = 4`, piso 3, escalando com a fonte — raio deixou de ser folga).
Item 17 fechado e verificado na imagem: em `c2_caixas_{claro,escuro}.png` a marcada tem **✓
branco sobre azul** e a indeterminada **– branco sobre cinza** — forma *e* matiz, WCAG 1.4.1
nível A satisfeito. O rádio marcado é um círculo cheio, forma distinta do quadrado.

Item 16 fechado, medido por mim na prancha: o `pressionado` **escurece nas duas peles** —
primário claro `#0a58ca → #0846a2`, primário escuro `#6ea8fe → #5886cb`, destrutivo escuro
`#e4665d → #b6524a`. O clareamento que lia como "recuar" acabou.

### 8. Estados vazios — **SOBREVIVE COM RESSALVA**

`qt/vazio.EstadoVazio` é um estado vazio de verdade: título em `TITULO`, frase em `AUXILIAR`
com quebra de linha, e **o botão que resolve, dentro do vazio**. Vi os três na tela (Texto,
Dataset, Galeria) e o quarto (Revisão) é condicional e correto.

E o item 3 está fechado sem ressalva: a frase da aba Texto — *"Use "Ler folha" para transcrever
a página aberta no visualizador, ou "Achar no texto…" para procurar numa folha já lida."* — se lê
**inteira** a 1920, 1366, 1280 e a 1063 (o piso), onde ela quebra em duas linhas. Os 77 px
cortados do ciclo 1 acabaram.

**A ressalva tem número.** O relatório §6 diz que a Galeria tinha três frases dizendo a mesma
coisa e que `lbl_posicao` "some agora". Medi as etiquetas visíveis ao mesmo tempo na Galeria:

```
y=  62  x=443  'livro ainda não varrido'
y= 364  x= 17  'Nenhum diagrama ainda'
y= 388  x= 17  'A Galeria mostra os diagramas que uma varredura já encontrou neste livro…'
```

**Continuam duas afirmações independentes de "nada foi varrido", a 302 px uma da outra** — contra
321 px no ciclo 1. Uma das três saiu; a redundância que o §7 mandou apagar ("**apague a segunda
mensagem**") continua lá, 19 px mais perto.

### 9. A pele escura — **SOBREVIVE. Continua projetada.**

Nada regrediu, e o item 16 melhorou a pele escura especificamente. Confirmo o que o ciclo 1
confirmou.

Duas ressalvas antigas, ambas ainda medíveis e nenhuma na ordem de serviço:

- **A pele "Foco" continua entregando menos superfície de trabalho.** Tabuleiro medido no pixel:
  **551 px (clara) contra 526 px (escura)** a 1920 — **−8,9 % de área**; e **318 contra 292** a
  1366×768 — **−15,7 % de área**. A fila de quatro pílulas do topo custa 34 px de altura e o
  tabuleiro paga.
- **Duas das quatro pílulas continuam sendo duplicatas de botões visíveis na mesma tela**:
  "Aplicar a FEN digitada" também está em (597, 529) e "Salvar a posição" em (65, 590) na mesma
  captura `c2_escuro_1366x768_resultado.png`.

---

## §3 — Reverificação dos portões (carta §6)

Rodei tudo, três vezes onde a carta manda três.

| portão | relatório C2 | minha medição | veredito |
|---|---|---|---|
| Contraste WCAG AA | 287 pares / 213 sob portão / 0 reprovados, folga mín. 3,27:1 e 3,03:1 | **idêntico**, nas duas peles | **CONFIRMADO** |
| Teclado + nome + papel | 0 de 214, seis abas `PASSOU` | **idêntico**: 24+52+30+39+20+49 = 214, `inalcancaveis: []` nas seis | **CONFIRMADO** |
| Progresso determinado/cancelável | 0 bloqueantes, 0 sem cancelamento, 0 sem rótulo | **idêntico** por execução do arnês | **CONFIRMADO no número, ver bloqueante nº 2** |
| Janela cabe em 1366×768 | `minimumSizeHint` 1063×735 / 1063×769; 1366×768 `OK` | **idêntico ao pixel**, nas duas peles | **CONFIRMADO** |
| Nome de livro de 149 chars | `minimumSizeHint` igual, 0 fora, 1 sobreposição | **idêntico**: 1063×735 nos dois casos, 0 fora, 1 par (987 px², o `QSpinBox`) | **CONFIRMADO** |
| fps ≥ 55 @ p95 | 92,7 (juntos) | **3 execuções: 84,8 · 85,0 · 86,6 → mediana 85,0** | **PASSA (55 % de folga), mas o 92,7 não reproduz** |
| Nada bloqueia a thread > 16 ms | REPROVA: virada 174–200 ms, abrir ~270 ms, "é PyMuPDF, e `pdf_io` não é desta frente" | REPROVA: **7 operações**, e a atribuição está errada em 34 % — **bloqueante nº 1** | **CONFIRMADO na falha, REFUTADO no diagnóstico** |
| Suíte do tronco | `3 failed, 4409 passed, 2 skipped, 28 warnings, 4301 subtests in 257.96s` | **`3 failed, 4409 passed, 2 skipped, 28 warnings, 4301 subtests passed in 257.20s`** | **CONFIRMADO, linha por linha** |
| ADR-0009 | 83 testes num venv sem Qt | **`83 passed in 0.48s`**; `find_spec` devolve `None` para os 7 bindings; varredura AST própria de **58** módulos de `ui/`: **0** imports de toolkit ou de `qt/` | **CONFIRMADO** |

### 3.1 "Vinte e oito testes do tronco e nenhum afrouxado" — **VERIFICADO, e a alegação se sustenta**

A coordenação pediu para checar isto especificamente. Fui atrás dos dois candidatos óbvios a
afrouxamento e **não achei afrouxamento em nenhum**:

- **`test_busy.SEM_REGISTRO` foi de 3 para 5 entradas** — as duas novas são exatamente as duas
  threads que este ciclo criou. Parece afrouxar, e não afrouxa: o teste é, por desenho anterior a
  este ciclo, uma lista de exceções **com motivo escrito** (*"Uma thread nova em `qt/` falha a
  suíte até estar registrada ou declarada aqui"*), e há um teste irmão
  (`test_a_lista_de_excecoes_nao_guarda_thread_que_nao_existe_mais`) que impede entrada morta. Os
  dois motivos escritos estão corretos: são leituras, e fechar a janela no meio não perde nada.
  **A consequência, porém, o construtor não ligou — e ela é o bloqueante nº 2.**
- **`test_packaging.LIMITE` subiu de 1863 para 1882 linhas.** A própria mensagem de falha da
  catraca autoriza: *"se o crescimento for deliberado, baixe o que for possível para `ui/` **ou
  registre o novo placar aqui e no ROADMAP, com o motivo**"*. O registro está lá, itemizado
  (2 + 4 + 13 = 19 linhas), e existe a contra-catraca
  `test_o_limite_registrado_nao_esta_defasado_para_baixo`. **Não é afrouxamento; é o mecanismo.**
- `test_ui_comandos.test_edicao_continua_com_um_primario` foi de "um primário **por grupo**" para
  "um primário **na tela inteira**" — isso é **apertar**, não afrouxar.
- `test_qt_painel_da_galeria.test_o_recorte_tem_o_lado_declarado` foi de "fixo em 420" para "entre
  240 e 420, e quadrado" — é o teste que o §7 do ciclo 1 **mandou atualizar pelo nome**.

**Registro sem reservas: procurei o afrouxamento e ele não está lá.**

### 3.2 Os dois bugs auto-infligidos — **os dois estão genuinamente limpos**

- **Os 1.486 `CR` soltos em `painel_de_texto.py`**: varri **todo** `src/` do tronco por bytes.
  **Zero arquivos com `CR` solto.** Em `painel_de_texto.py`: `CR = 1486`, `CRLF = 1486`,
  `LF = 1486`, 1.486 linhas — **todo `CR` está pareado**. Limpo.
- **O estado vazio da Galeria como três colisões**: `sobreposicao.py` devolve
  **1 par sobreposto (987 px², o `QLineEdit` interno do `QSpinBox`, que o §7 isenta)** e
  **0 controles fora da janela**, com o nome curto e com o de 149 caracteres. A `QStackedLayout`
  resolveu. Limpo.

---

## §4 — Defeitos bloqueantes

### 1. Virar de página relê o `labels.csv` inteiro na thread da interface — 57,7 ms de 171,4 ms (34 %), 3,6× o portão — e o relatório atribui o resíduo inteiro ao PyMuPDF, que "não é desta frente".

**Onde:** `qt/janela.py:1579 _aviso_de_treino`, chamado a cada virada de página.

**A cadeia, medida (`quem_chama.py`), idêntica nas duas viradas que instrumentei:**

```
qt/painel_do_pdf.py:702  desenhar_pagina  → pagina_desenhada.emit()
qt/janela.py:1061        _pagina_apareceu → self.campo.atualizar()
qt/campo.py:159          atualizar        → lbl_estado.setText(...)
qt/janela.py:1579        _aviso_de_treino → pages_with_training_samples(LabelStore(csv).read(), …)
labels.py:380            LabelStore._load_rows  ← 5.431 linhas × 20 colunas
```

**Os quatro primeiros quadros são `qt/`. São desta frente.**

**O que medi**, sem perfilador, neutralizando só a leitura (`custo_aviso.py`, 6 viradas de cada
lado, mediana):

| | viradas (ms) | mediana |
|---|---|---|
| com a leitura do `labels.csv` | 170,8 · 170,4 · 174,2 · 170,3 · 192,6 · 172,1 | **171,4** |
| sem ela | 114,1 · 110,6 · 118,0 · 110,1 · 113,3 · 120,7 | **113,7** |

**Custo: 57,7 ms por virada — 34 % da virada, e 3,6× o portão de 16 ms sozinho.**

Confirmação independente por thread (`qual_thread.py`): `labels._clean` é chamado
**108.620 vezes na `MainThread`** (5.431 × 20) em **cada** virada, nas três que medi.

**Por que o arnês não viu:** `bloqueio.py` publica `pilha_do_pior`, que é **uma amostra**. A
chamada única de 77 ms do `fz_run_display_list` é o maior bloco contíguo e ganha a amostra em 5
de 6 vezes; 57,7 ms espalhados por 108.620 chamadas Python minúsculas nunca ganham. **É o
terceiro portão medindo a coisa errada** — e foi dessa amostra que saiu o diagnóstico do §3 do
relatório.

**O que o relatório diz** (§3, linha do item 5 parcial): *"virar de página: 174-200 ms; abrir
livro: ~270 ms | é `PyMuPDF` de verdade mais `realpath`, e `pdf_io` não é desta frente."*
Está errado para 34 % do custo, e os 34 % são código desta frente.

**E o código sabia.** O docstring de `_aviso_de_treino` argumenta: *"mesmo motivo que não seria no
`Ctrl+S` (S-116): virar página é um gesto por vez, e não o laço interno."* Uma leitura de arquivo
inteiro na thread da janela, justificada por escrito, numa frente cujo portão titular é 16 ms. E
`LabelStore(csv_path).read()` **constrói uma instância nova a cada chamada**, o que mata qualquer
cache de instância por construção.

**Como reproduzir:**
```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\c3\custo_aviso.py "…\1937 Kemeri.pdf"
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\c3\quem_chama.py  "…\1937 Kemeri.pdf"
```

**Por que reprova:** carta §6, honestidade de medição — é **exatamente** o defeito nº 5 do ciclo
1 ("a pilha publicada não é a que o instrumento devolve, e o plano de conserto foi escrito contra
a pilha errada"), na mesma frente, sobre a mesma biblioteca, num terceiro ponto de chamada. O
construtor fechou `_carregar_marcas_salvas` e `contagem_de_amostras` e deixou o que dispara **a
cada gesto** em vez de uma vez por livro. E o custo cresce com o dataset: 5.431 linhas hoje custam
57,7 ms; o `labels.csv` existe para crescer.

### 2. A barra de progresso do rodapé é uma caixa vazia permanente, e as duas operações longas que este ciclo criou não registram progresso nem cancelamento — o portão não as vê porque ele só enxerga quem se registra.

**Onde:** `qt/rodape.py:131-140`; `qt/marcas.LeitorDeMarcas.pedir` e
`qt/painel_do_dataset._reler_agora`.

**O que**, sondado na janela viva (`detalhes.py`) **com nada rodando**:

```
QProgressBar  visivel=True  x=1712 y=1051  120x26  faixa=0..100  valor=0  texto_visivel=False
botao Cancelar: habilitado=False
```

`grep setVisible|hide|show` em `qt/rodape.py` devolve **vazio**: a barra **nunca se esconde**. O
resultado está nas 36 capturas, no canto inferior direito de todas: um retângulo arredondado
vazio, com borda de 1 px e raio de 4 — **desenhado exatamente como um campo de texto vazio** —
ao lado de um `Cancelar` desabilitado. Recortes ampliados 4×:
`benchmarks\reports\critique\ui\c3\z_progresso_{claro,escuro}.png`.

E o que ele deveria estar mostrando, ele não mostra. Nas 12 capturas de 1280 e 1366 a barra de
status diz **"Lendo o dataset…"** — a leitura assíncrona que o item 5 criou está correndo — e a
barra continua em **0 de 100, sem texto, com o `Cancelar` desabilitado**. Confirmei a causa:
`painel_do_dataset.py:393` faz `self.estado.emit("Lendo o dataset…")` e **não** chama
`busy.register`. Só 5 operações da janela inteira registram (`dialogos` ×2, `exportador`,
`painel_da_galeria`, `painel_de_texto`, `painel_do_dataset:654`), e nenhuma é uma das duas novas.

**Por que o portão diz `PASSOU`:** `caissa.ui.audit.progresso` é uma varredura AST dos pontos de
chamada de `busy.register`. **Uma operação que nunca se registra é invisível para ele.** O
inventário devolve 6 linhas e nenhuma é a leitura do dataset. O portão que existe para achar
"operação longa sem cancelamento" não pode achar a operação longa sem cancelamento que este
ciclo criou.

E a declaração em `test_busy.SEM_REGISTRO` (§3.1) resolve **uma** pergunta — "perde trabalho ao
fechar?", não — e foi usada para responder **outra** — "precisa de indicação de progresso?". São
perguntas diferentes e o construtor as juntou.

**Por que reprova:** carta §3.3 — *"Barra de progresso indeterminada onde o total é conhecido"*
(aqui é pior: determinada, congelada em zero, com o total 5.431 escrito no próprio rótulo da aba)
e *"Operação longa sem cancelamento"*. E o item 7 do §7 do ciclo 1 pedia *"cancelamento nas duas
operações longas, **e publique a contagem que o arnês devolve**"* — a contagem publicada é
honesta e o arnês deixou de contar duas.

### 3. A prancha de estados construída para consertar o defeito nº 8 do ciclo 1 desenha o `hover` idêntico ao repouso — nas 8 imagens, nas 4 linhas, nas 2 peles — e o relatório afirma por escrito o mecanismo que evitaria exatamente isso.

**Onde:** `benchmarks/reports/ui/estados_{claro,escuro}_foco{0,1,2,3}.png`;
`src/caissa/ui/audit/amostrario.py:233-255`.

**O que:** diferenciei a célula "sob o ponteiro" contra a célula "repouso", região inteira, nas 8
pranchas:

| papel | pixels diferentes de repouso | ΔRGB máx |
|---|---|---|
| NEUTRO — **hover** | **0 de 6.240 (0,0 %)** | **0** |
| NEUTRO — pressionado | 4.995 (80,0 %) | 249 |
| NEUTRO — com foco | 1.338 (21,4 %) | 249 |
| NEUTRO — desabilitado | 5.382 (86,2 %) | 237 |
| PRIMARIO — **hover** | **0 de 5.616 (0,0 %)** | **0** |
| DESTRUTIVO — **hover** | **0 de 5.408 (0,0 %)** | **0** |
| campo — **hover** | **0 de 5.408 (0,0 %)** | **0** |

`ΔRGB máx = 0` nas **8** pranchas (`foco0..3` × claro/escuro). Todos os outros estados diferem
entre 8,6 % e 99,7 % dos pixels — só o `hover` é byte a byte igual ao repouso.

**O relatório §2.8 descreve este resultado e afirma tê-lo evitado:** *"`WA_Hover` é o que faz a
coluna 'sob o ponteiro' repintar; sem ele ela sairia idêntica à de repouso, que é o defeito do
ciclo 1 com outra causa."* O `amostrario.py` faz `setAttribute(WA_Hover, True)` e envia
`QEvent.Type.Enter` + `HoverEnter` sintéticos — e o QSS não pinta `:hover` sem
`QStyle::State_MouseOver`, que evento sintético não liga.

**O produto está certo, e digo isso com clareza:** `ui/folha_de_estilo.py` declara `:hover` em
botão (linha 309), item de lista, cabeçalho, indicador de caixa, barra de rolagem, aba, divisor e
régua. O `hover` existe na aplicação. **O que não existe é a prova.**

**Por que reprova:** é literalmente o defeito nº 8 do ciclo 1 — *"a prancha que a carta §3.1
manda olhar afirma no rótulo algo que a imagem não contém… Uma prova errada é pior que prova
nenhuma"* — reencarnado no artefato construído para fechá-lo, com o relatório afirmando o
contrário. Carta §6. É o mais barato dos três: é uma linha de arnês.

---

## §5 — Defeitos não bloqueantes

1. **O item 13 não é um limite geométrico; é uma escolha de leiaute.** A aritmética do construtor
   está certa — um quadrado num retângulo 933×559 não passa de 59,9 % — mas o canvas é 933 de
   largura porque **há 180 px de nada entre o tabuleiro e a paleta de peças**. Medido em
   `c2_claro_1920x1080_resultado.png`: `vão entre tabuleiro e paleta = 180×580 = 104,4 kpx a
   **0,17 %** de tinta`, mais `90×300 = 27,0 kpx a 0,33 %` abaixo da paleta. **131 kpx = 24 % do
   canvas, vazios.** O vão é **duas vezes a largura da paleta**. Encostar a paleta no tabuleiro dá
   um canvas de ~665×580 e um tabuleiro de 568 px: **≈83 % de ocupação**, o alvo do §7, sem tocar
   em geometria nenhuma. A explicação é conveniente, não física.
2. **Item 12 confirmado não fechado, e a contagem do construtor é honesta.** Contei nas capturas:
   **28 botões em 4 filas** na aba Estudo, contra o alvo de ≤ 12 em ≤ 2. E `.md` / `.html` /
   `.rtf` continuam sendo três botões de barra permanentes (não bloqueante nº 9 do ciclo 1).
3. **O arnês devolve 7 operações violando o portão e o relatório nomeia 2.** Mediana de `pior_ms`
   em 3 invocações: virada p.42 **192,2**, abrir PDF **262,6**, virada p.41 **188,1**, virada
   p.121 **286,7**, rasterizar 300 DPI **75,7**, aba Dataset **89,1**, **aba Galeria 25,3**. A
   última não aparece em lugar nenhum do relatório.
4. **A pilha do "abrir PDF" não é estável, e o relatório publica uma como se fosse *a* pilha.** Em
   3 execuções: `estudo_arquivo.chave_de → Path.resolve → stat`;
   `painel_da_galeria._abrir_cache_de_posicoes → games_cache.database_fingerprint → stat`;
   `painel_de_estudo.abrir_livro → estudo_arquivo.carregar → Path.exists → stat`. **Três pilhas,
   um substrato** (`stat` de sistema de arquivos) — a substância da explicação está certa, a
   especificidade está inventada. E a aritmética desmente a moldura "é rasterização": o
   `render_pdf_page` medido sozinho é **75,7 ms** dos **262,6 ms** da abertura; os outros **187 ms
   (71 %)** são toques de disco em `qt/` e `estudo_arquivo`.
5. **A afirmação "nenhum comando perdeu alcance — `ui/atalhos.py` mantém as teclas" é falsa para
   os cinco comandos sobre os quais ela é feita.** Medi `ui/atalhos.por_acao` (21 ações com tecla):
   `exportar_pgn`, `cancelar_exportacao`, `marcar_diagramas`, `roda_vira_pagina` e
   `abrir_no_leitor` — **nenhum tem tecla**. Não havia tecla para manter. O alcance pelo menu é
   real e o item 11 continua fechado; a frase é que está errada.
6. **O divisor colapsa e leva a navegação inteira junto, com um alvo de 3 px e sem volta na
   sessão.** `QSplitter::handle:horizontal { width: max(3, 2)px }` = **3 px**, pintado com a cor
   de separador (só fica azul no `hover`), e `setChildrenCollapsible` nunca é chamado — fica o
   `True` de fábrica. Medido (`colapso.py`, janela 1366×768): colapsar o painel esquerdo põe
   **21 de 36 botões fora da janela** e apaga a faixa de abas inteira (captura:
   `c3_colapso_esquerdo.png`); colapsar o direito põe **14 de 36** fora. `minimumSizeHint`
   continua 1063×735 — o leiaute não empurra de volta. Nenhum item de menu restaura o painel (o
   menu `Ver` tem página, zoom, marcas, aparência e densidade). **Atenuante que registro:** um
   `sash_fraction` gravado em 0,0 é indistinguível de "nunca gravado"
   (`janela.py:245 bool(0.0)`), então **reabrir o programa devolve o painel**. O estrago é da
   sessão, não permanente.
7. **A coluna "Motivo" da Revisão continua elidida, e piorou um pouco**: **16 de 27 linhas a
   1920** (eram 14) e **27 de 27 a 1366 e a 1280**. É o texto que diz por que o item está na fila.
8. **A tabela do Dataset precisa de barra de rolagem horizontal a 1280 e a 1366**, e o cabeçalho
   "Conjunto" sai cortado em "Conjunt" (1366) e "C" (1280). As colunas que empurram são as que o
   ciclo 1 mediu como constantes ("Livro", "Pag.", "Criado em" com `—` em 5.431 linhas).
9. **Um nome acessível é uma frase de ajuda truncada, e ele está nas seis abas.** O `QComboBox` de
   regime (`qt/campo.py:110`) não tem `accessibleName`; a cascata cai na dica e o arnês registra
   `"Em que condição esta página foi lida. Entra na anotação e separa as"` — **67 caracteres
   terminando no meio da frase**, em `#14` da ordem do `Tab` das seis abas. O portão do item 1 tem
   quatro motivos (eco do papel, menos de três letras, repetido na aba, o próprio valor) e **nenhum
   cobre "isto é prosa, não é nome"**. É a quinta regra que falta.
10. **`DialogoDeTreino: barra fixa em indeterminada`** aparece no inventário com
    total **NÃO** / determinada **NÃO** / cancelável **NÃO**, e não entra na contagem de "sem
    cancelamento" porque o filtro é `especie == "registro"` e ela é `"barra"`. Ou ela é coberta
    pelo registro de `dialogos.py:740` (e então o inventário devia dizê-lo) ou é a terceira
    operação sem cancelamento.
11. **O 92,7 fps não reproduz.** Três execuções minhas com a máquina ociosa: **84,8 · 85,0 ·
    86,6 → mediana 85,0 @ p95**, em linha com os 86,9 do ciclo 1 e 8 % abaixo do publicado. O
    portão é 55 e passa com 55 % de folga nas três — registro por honestidade de medição, não como
    problema.
12. **A janela continua recusando 1024×768 e 800×600**: `1063×735` (clara) e `1063×769` (escura),
    **39 px de largura e 35–69 px de altura acima do alvo de ≤ 1024×700**. Declarado pelo
    construtor com a causa isolada (a coluna de headers da Galeria pede 516 px). Confirmo os dois
    números e a causa.
13. **Os botões de formato da aba Texto não mostram o que fazem**: `Negrito`, `Itálico`,
    `Sublinhado` e `Tachado` são quatro retângulos com texto 12 px peso 400 idêntico. Toda a
    referência desenha cada um no estilo que ele aplica.
14. **`Modo bloco (lento)`** continua sendo uma caixa de seleção cujo rótulo admite que a opção é
    lenta sem dizer quanto nem quando usá-la (não bloqueante nº 10 do ciclo 1, intocado).
15. **Dois controles sem rótulo visível na aba Texto** (um spinner `1` e um combo `auto`, em
    x=13..172), e um campo sem rótulo na coluna "Cabeçalhos do PGN" (abaixo de `outro`). Têm nome
    acessível; não têm rótulo na tela.
16. **Casos ruins que passaram e eu registro como crédito:** o livro de **289 páginas** no spinner
    de página — 75 px, texto `289`, **sem refluxo** (e 81 px com `9999`); **nenhum rótulo cortado**
    nas seis abas (varri `QPushButton`/`QLabel` visíveis comparando `QFontMetrics.horizontalAdvance`
    contra a largura do widget — o único que "não cabe" é a frase do estado vazio da Galeria, que
    **quebra em duas linhas**, que é o comportamento certo).

---

## §6 — O que funciona, e o que este ciclo conquistou

A carta §5.5 manda nomear. Nomeio, e desta vez é muito:

1. **A janela cabe na tela do laptop.** Era o defeito nº 4 do ciclo 1 e era o mais grave.
   `minimumSizeHint` caiu de **1243×890 para 1063×735**, 1366×768 é aceito nas duas peles, e o
   censo de controles abaixo de y=730 caiu de **13–37 % por aba para 1 por aba (1,9–3,6 %), que é
   o rodapé**. Vi na captura: em Revisão, `Corrigir agora / Marcar revisado / Pular / Reabrir /
   Próximo pendente` estão na tela; no Dataset, `Abrir no editor / Conferir com o modelo /
   Quarentena / Remover` também.
2. **A barra do visor virou um mapa.** De **16 controles em 4 filas a 1920 e 6 a 1243, com 14/16
   trocando de fila**, para **12 controles em 2 filas de 1243 a 1920, com 0/12 trocando**. Quatro
   blocos nomeados com separador de 1 px. Reproduzi as seis larguras. É o melhor item de desenho
   do ciclo e não tenho nenhuma ressalva a fazer a ele.
3. **O nome do arquivo deixou de determinar a largura da aplicação.** 1063×735 com
   `1937 Kemeri.pdf` e 1063×735 com os 149 caracteres — **iguais ao pixel** — contra 1243 e 1513.
   Zero controles fora, uma sobreposição (a isenta). E o construtor achou sozinho o segundo
   culpado (a zona do documento no rodapé, 996 px), que o ciclo 1 não tinha visto.
4. **O congelamento de 1,3 segundo acabou.** Aba Dataset, execução fria: de **1.302 ms para
   89,1 ms** medidos por mim (o construtor reportou 107). E o arnês foi consertado antes do
   conserto — `viola` olha `max()` e a tabela imprime `pior_ms` com `frio` e `mediana` ao lado, que
   era o item 6 e era a pré-condição para tudo.
5. **A caixa de seleção marcada tem um ✓ e a indeterminada um –**, com um par novo no checador
   (287/213 contra 286/212), que é a checagem de WCAG 1.4.1 que o item 17 pediu. Verificado na
   imagem.
6. **O `pressionado` escurece nas duas peles.** Medido: `#0a58ca→#0846a2`, `#6ea8fe→#5886cb`,
   `#e4665d→#b6524a`.
7. **Uma margem esquerda, em seis abas, 143 controles: 10 px.**
8. **A fronteira `ui/` × `qt/` sobreviveu ao ciclo.** 58 módulos, 0 imports de toolkit por
   varredura AST minha, 83 testes verdes em 0,48 s num venv sem binding. Os quatro módulos novos
   (`escala`, `marcas`, `rotulo`, `vazio`) são todos de `qt/`. **Esta é a coisa mais valiosa da
   frente e ela continua intacta.**
9. **A suíte do tronco empatou, e eu reproduzi a linha final byte a byte.** Procurei
   afrouxamento nos dois testes que mais pareciam afrouxados e não o encontrei (§3.1).
10. **Os dois bugs auto-infligidos estão limpos**, e o construtor os publicou. Esse é o
    comportamento certo e deve continuar.

O trabalho deste ciclo foi de desenho, não só de conformidade, e **isso era exatamente o que o
ciclo 1 disse que faltava**. A frente andou muito.

---

## §7 — O que precisa mudar para eu aprovar

Três itens bloqueantes. Nenhum é grande.

### Bloqueantes

1. **Tire a leitura do `labels.csv` da virada de página.** `qt/janela.py:1579 _aviso_de_treino`
   constrói um `LabelStore` novo e lê 5.431 linhas a cada `_pagina_apareceu`. Use a **mesma
   técnica que este ciclo já aplicou em `contagem_de_amostras`**: guardar por `(tamanho, mtime)`
   do arquivo. É uma memoização, não uma thread.
   *Alvo: virada de página ≤ 116 ms (a mediana sem a leitura que eu medi), e `labels`/`csv` com
   zero chamadas na `MainThread` durante `ir_para_pagina`, cobrado por `quem_chama.py`.*
   E **corrija o §3 do relatório**: a virada não é "PyMuPDF e não é desta frente"; ela é
   **77 ms de PyMuPDF + 57,7 ms de `qt/`**.

2. **Acrescente ao `bloqueio.py` uma atribuição que sobreviva a mil chamadas pequenas.** A
   `pilha_do_pior` é **uma amostra** e por isso sempre premia o maior bloco C contíguo. Publique,
   ao lado dela, o **tempo próprio por módulo** da janela bloqueada (um `cProfile` por operação
   basta — `atribuicao.py` faz isso em 60 linhas).
   *Alvo: o relatório do arnês, sozinho, mostrar que a virada de página tem custo em `qt/` sem
   ninguém precisar escrever um instrumento novo.*

3. **Registre as duas leituras assíncronas e faça o rodapé dizer a verdade.**
   - `qt/marcas.LeitorDeMarcas.pedir` e `qt/painel_do_dataset._reler_agora` devem chamar
     `busy.register` com `total` (o número de linhas é conhecido: está no rótulo da aba) e
     `cancel` de verdade. A entrada em `test_busy.SEM_REGISTRO` responde "não perde trabalho ao
     fechar" e **não** responde "não precisa de progresso" — são duas perguntas.
   - `qt/rodape.py`: a barra **tem de se esconder quando não há nada a mostrar**. Hoje ela é
     `visivel=True, valor=0, texto_visivel=False`, permanente, nas 36 capturas, desenhada como um
     campo de texto vazio.
   *Alvo: `caissa.ui.audit.progresso` listar 8 operações e não 6; e zero pixels de barra na janela
   ociosa, cobrado pelo censo de tinta do rodapé.*

4. **Conserte a prancha de estados.** `amostrario.py` manda `Enter`/`HoverEnter` sintéticos e o
   QSS não pinta `:hover` sem `State_MouseOver`. Force o estado ao pintar (`QStyleOption` com
   `State_MouseOver`, ou `QStyle::drawControl` com a opção montada à mão), **ou** apague a coluna.
   *Alvo: `ΔRGB máx` entre a célula "sob o ponteiro" e a de repouso **maior que zero** nas 8
   pranchas — cobrado por teste, porque este é o segundo ciclo em que a prancha mente.*

### De desenho — não bloqueiam, e são o que separa "passa no portão" de "trocaria de ferramenta"

5. **Dê à aba a ênfase dela.** Hoje a única primária da janela é `Ler o melhor diagrama` e ela
   está no visor: **6 de 6 abas sem ação primária própria**. Ou `conferir_tela` passa a permitir
   **uma por painel de aba além da do visor**, ou as ações de aba ganham a tecla que o §7 do ciclo
   1 pediu — `corrigir_agora`, `anotar_pagina` e `estudo_do_diagrama` estão hoje **sem tecla
   global** (medido em `ui/atalhos.por_acao`).

6. **Abra a escala de tipos.** `AUXILIAR/CORPO/TITULO` = **11/12/13 px** são degraus de +9 % e
   +8 %, e o ciclo 1 já tinha escrito que 8 % não produz hierarquia. Uma razão de ~1,2 dá
   **11 / 13 / 16 px**. E aplique `AUXILIAR` aos textos de apoio que ainda são corpo: hoje
   **99 de 107 widgets (92,5 %) são 12 px / 400 / uma família**.
   *Alvo: ≤ 80 % dos widgets visíveis numa única combinação, no censo de `sonda.py`.*

7. **Encoste a paleta de peças no tabuleiro.** São **180×580 = 104,4 kpx a 0,17 % de tinta** entre
   os dois, mais 27,0 kpx abaixo da paleta — 24 % do canvas. Fechar o vão dá um canvas de ~665×580
   e um tabuleiro de ~568 px. *Alvo: ocupação ≥ 80 % em Resultado, que é o alvo original do item
   13, alcançável sem tocar em `MAX_DO_TABULEIRO`.*

8. **Faça o visor reajustar a página ao redimensionar.** Ela renderiza **366 px de largura a 1280,
   1366 e 1920** — o mesmo pixel — e a 1920 ocupa **29 % de um viewport de 819×850**. *Alvo: a
   página ≥ 60 % da largura do viewport nas três resoluções, sem o usuário clicar em nada.*

9. **Encolha a tabela da Revisão ao número de linhas, ou traga a fila de ações para junto do
   dado.** Com os 27 itens que a aba tem: **1048×376 = 394,0 kpx a 0,00 %** de corpo de tabela não
   usado, e 424 px entre a última linha e `Corrigir agora`.

10. **Apague a terceira frase da Galeria.** `'livro ainda não varrido'` (y=62) e
    `'Nenhum diagrama ainda'` (y=364) dizem a mesma coisa a **302 px** uma da outra. O §7 do ciclo
    1 pediu isto e ele foi feito pela metade (eram três, são duas).

11. **Alinhe `Gravar` com os quatro botões abaixo dele**: x=892 contra x=829, largura 155 contra
    218, numa pilha de cinco.

12. **Não deixe o divisor apagar a navegação.** `setChildrenCollapsible(False)` no divisor
    principal (ou um piso de ~120 px por lado) e uma alça de **6–8 px** em vez de 3.
    *Alvo: zero controles fora da janela com a alça em qualquer posição, cobrado por `colapso.py`.*

13. **Acrescente o quinto motivo ao portão de nomes:** um nome que é **prosa** (contém ponto final
    seguido de espaço, ou passa de ~40 caracteres) não é nome. Hoje o `QComboBox` de regime é
    anunciado, nas seis abas, por 67 caracteres que terminam em "separa as".

---

## §8 — Como reproduzir tudo

```bash
# Fase 2 — os portões (contraste e progresso no venv da suíte; o resto no do tronco)
.venv\Scripts\python.exe -m pytest tests\unit\ui\ -q
.venv\Scripts\python.exe -m caissa.ui.audit.contraste
.venv\Scripts\python.exe -m caissa.ui.audit.progresso
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts& set PYTHONPATH=<suite>\src
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado  --pdf "…\1937 Kemeri.pdf"
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio --pdf "…\1937 Kemeri.pdf"   # 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.quadros  --pdf "…\1937 Kemeri.pdf"   # 3x, máquina ociosa
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py tudo
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\sonda.py tipografia
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\casos_ruins.py {classica,foco}
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\sobreposicao.py
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q          # no tronco

# Fase 3 — os instrumentos deste ciclo (benchmarks\reports\critique\ui\c3\)
custo_aviso.py   <pdf>   # o bloqueante nº 1: 171,4 ms com a leitura, 113,7 sem
quem_chama.py    <pdf>   # a cadeia qt/ -> LabelStore._load_rows, por thread
qual_thread.py   <pdf>   # 108.620 chamadas de labels._clean na MainThread por virada
atribuicao.py    <pdf>   # tempo próprio por módulo (o que a pilha_do_pior não vê)
colapso.py       <pdf>   # 21 de 36 botões fora da janela com o painel colapsado
detalhes.py      <pdf>   # o desalinho de 63 px, as duas frases, a barra em 0/100
medidas_c3.py    tabuleiro|regiao|pagina <png…>   # geometria e tinta sobre as capturas
```

Artefatos meus em `benchmarks\reports\critique\ui\c3\`: os sete instrumentos,
`bloqueio_c3.txt`, `medir_c2_c3.txt`, `tronco_pytest.txt`, os recortes 4×
`z_progresso_{claro,escuro}.png` e as capturas `c3_colapso_{esquerdo,direito}.png`.

---

## §9 — Veredito

**REPROVADO — e por pouco.**

Reproduzo **quinze dos dezoito** itens com número próprio, incluindo os três que o ciclo 1 deu
como razões para reprovar. A janela **cabe** no laptop de 1366×768 (1063×735, um controle abaixo
de y=730 e ele é o rodapé). Ela **não quebra** com o nome de 149 caracteres (mesmo
`minimumSizeHint` ao pixel, zero controles fora). A barra do visor virou **duas filas com zero
refluxo entre 1243 e 1920**, que é o melhor trabalho de desenho da frente. O congelamento de
1,3 segundo virou 89 ms. E procurei especificamente o afrouxamento de teste que a coordenação
apontou como o pior modo de falha: **fui aos dois candidatos e não o encontrei** — a catraca de
linhas e a lista de exceções de threads foram usadas pelos mecanismos que elas próprias escrevem.

Não aprovo por três motivos, e os três são pequenos e localizados:

- **O `csv` voltou por uma terceira porta, e o relatório o atribui a outra frente.** Virar de
  página relê 5.431 linhas na thread da janela: **57,7 ms de 171,4 ms, 34 %, 3,6× o portão**, por
  uma cadeia cujos quatro quadros são todos `qt/`. O relatório diz "é `PyMuPDF` de verdade, e
  `pdf_io` não é desta frente". **É exatamente o defeito nº 5 do ciclo 1**, na mesma frente, sobre
  a mesma biblioteca, e por exatamente a mesma causa instrumental: uma pilha de **uma amostra**
  que sempre premia o maior bloco C contíguo. Deixar passar duas vezes ensina que a
  desatribuição funciona.
- **As duas operações assíncronas que este ciclo criou não têm progresso nem cancelamento, e o
  portão não pode vê-las** porque ele só enxerga quem chama `busy.register`. O que o usuário vê é
  uma **caixa vazia permanente** de 120×26 no canto inferior direito de todas as 36 capturas,
  desenhada como um campo de texto, ao lado de um `Cancelar` desabilitado.
- **A prancha construída para consertar o defeito nº 8 do ciclo 1 desenha o `hover` idêntico ao
  repouso** — ΔRGB máximo **zero**, nas 8 imagens — e o relatório afirma por escrito o mecanismo
  que teria evitado isso. O produto tem `hover`; a prova, não.

Os itens 1 a 4 do §7 são um `mtime`, um `cProfile`, dois `busy.register` mais um `setVisible`, e
uma `QStyleOption`. Se eles estiverem fechados e a atribuição do §3 do relatório for reescrita
com os números certos, **aprovo** — os itens 5 a 13 são de desenho e podem viver num ciclo
seguinte sem bloquear ninguém.
