# F9 — Interface (Qt) — relatório do **ciclo 2**

Resposta à ordem de serviço do §7 de `docs/quality/F9_CRITIQUE_C1.md`. Dezoito itens, um a um,
com o número de partida (o do crítico), o número de chegada (medido agora), o veredito, e **quem
fez** — porque metade do ciclo 2 foi feita por um agente anterior que morreu antes de escrever o
relatório dele, e a primeira coisa que este ciclo teve de fazer foi descobrir o que já estava
pronto.

**Todo número deste documento saiu de um comando.** O §7 lista os comandos e os arquivos.

---

## §0 — O que o predecessor deixou pronto, e como eu descobri

O agente do ciclo 2 anterior foi interrompido por limite de taxa depois de tocar **catorze
arquivos** e antes de escrever uma linha de relatório. As últimas palavras dele diziam que ia
começar os itens 8/15/16/17 da numeração do encarregado (escala tipográfica, `pressed` escuro,
símbolo da caixa, raio de canto). Reconstruí o que ele tinha feito por `mtime` e por leitura:

| arquivo | quando | o que ele fez |
|---|---|---|
| `caissa/ui/audit/teclado.py` | 17:17 | **o portão que faltava**: `nome_vazio_de_sentido`, com os quatro motivos |
| `caissa/ui/audit/bloqueio.py` | 17:15 | **`viola` passou a olhar `max()`** em vez da mediana |
| `chess_diagram_ocr/ui/nomes_acessiveis.py` + `qt/acessibilidade.py` | 17:19 | a cascata de nome acessível, com `CLASSES_COM_VALOR` |
| seis painéis do `qt/` | 17:20-17:23 | nomes acessíveis explícitos nos controles que a cascata não alcança |
| `chess_diagram_ocr/ui/folha_de_estilo.py` | 17:27 | `RAIO_NA_BASE = 4` e `ESCURECIMENTO_DO_PRESSIONADO = 0.20` |

Ou seja: ele fechou os **portões** dos itens 1 e 2 e dois dos quatro itens de folha de estilo
(17 e 15 da numeração do encarregado). Ele **não** fez o conserto do item 2 (as leituras de CSV
continuavam na thread da janela), não fez o símbolo da caixa de seleção, e não aplicou a escala
tipográfica -- o censo continuava devolvendo duas combinações.

E ele deixou **duas regressões** na suíte do tronco que eu tive de fechar: `#ffffff`/`#000000`
cravados em `ui/folha_de_estilo.py` (`test_so_o_modulo_de_tokens_escreve_hexadecimal`) e
`qt/janela.py` acima da catraca de linhas.

---

## §1 — O placar

| # (§7) | item | partida | chegada | veredito |
|---|---|---|---|---|
| 1 | nome que nomeia em todo controle | 34 de 256 sem sentido | **0 de 214**, seis abas `PASSOU` | **fechado** |
| 2 | elidir o rótulo do livro | `minimumSizeHint` 1243 → **1513**; 1 controle fora; 4 sobreposições | **1063×735 para qualquer nome**; 0 fora; 1 sobreposição (a isenta) | **fechado** |
| 3 | a dica do estado vazio cabe | cortada em **77 px** a ≤ 1350 px | **0 px cortados** de 1920 a 1063 | **fechado** |
| 4 | a janela cabe em 1366×768 | **RECUSOU**; 13 % a 37 % dos controles abaixo da borda | **1366×768 `OK` nas duas peles**; **1 controle por aba (1,9 % a 3,6 %)** | **fechado com ressalva** |
| 5 | tirar o `csv` das duas threads de interface | Dataset **1.302 ms** frio; abrir PDF **250 ms** em `csv` | Dataset **107 ms** frio (23-26 quente); abrir PDF **sem `csv` na pilha** | **fechado** |
| 6 | o arnês olha o pior, não a mediana | `viola` pela mediana; tabela pela mediana | `viola` e **tabela** pelo pior; frio e mediana ao lado | **fechado** |
| 7 | cancelamento nas duas operações longas | 2 sem cancelamento, 1 defeito bloqueante, 2 sem rótulo | **0, 0 e 0** | **fechado** |
| 8 | a prancha de controles | `hover` e `pressed` sem imagem; rótulo "Com foco" mentindo | **3 papéis × 5 estados × 2 peles**, 8 capturas | **fechado** |
| 9 | usar a escala tipográfica | 2 combinações, `TITULO` em zero widgets | **3-4 combinações por aba**, 3 tamanhos e 2 pesos nas 12 (aba × pele) | **fechado** |
| 10 | uma ênfase por tela | 3, 3, 3, 2, 2, 2 | **1 em todas as seis** | **fechado** |
| 11 | agrupar a barra do visor | 16 controles, 4 e 6 filas, **14/16** trocando | 12 controles em **4 blocos**, **2 filas em toda largura**, **0/12** trocando | **fechado** |
| 12 | a aba Estudo: 46 botões em 4 filas | 46 botões, 4 filas | **28 botões**, 4 filas | **não fechado** — ver §3 |
| 13 | teto para o tapete do tabuleiro | tapete **10,9 %** da janela contra 9,4 % do tabuleiro | tapete **1,31 %** contra **14,69 %**; ocupação 58,3 % e 80,8 % | **fechado em parte** — ver §3 |
| 14 | três estados vazios de verdade | Galeria 0,24 %, Texto 0,57 %, Revisão 0,00 % de tinta | **4 estados vazios** com título, frase e botão | **fechado** |
| 15 | uma margem esquerda | 8, 9, 12 e 13 px | **10 px nas seis abas**, de `espaco.margem_da_aba()` | **fechado** |
| 16 | `pressed` escurece nas duas peles | escuro clareava (`#6ea8fe → #98c1fe`) | escurece; ver `estados_escuro_foco*.png` | **fechado** (predecessor) |
| 17 | símbolo na caixa marcada | quadrado cheio × quadrado cheio, só a matiz separa | **✓ e –** desenhados, nas duas peles | **fechado** |
| 18 | raio de canto 2 → 4-5 px | 1 px de mistura no canto | `RAIO_NA_BASE = 4` | **fechado** (predecessor) |

**Quinze fechados, um fechado com ressalva, um fechado em parte, um não fechado.**

---

## §2 — Item a item

### 1. Nome que nomeia — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado --pdf "...\1937 Kemeri.pdf"
```

```
  Resultado      24 focáveis    24 pelo Tab  fecha   0 sem nome  0 sem papel  0 nome vazio  PASSOU
  Estudo         52 focáveis    52 pelo Tab  fecha   0 sem nome  0 sem papel  0 nome vazio  PASSOU
  Revisão        30 focáveis    30 pelo Tab  fecha   0 sem nome  0 sem papel  0 nome vazio  PASSOU
  Texto          39 focáveis    39 pelo Tab  fecha   0 sem nome  0 sem papel  0 nome vazio  PASSOU
  Dataset        20 focáveis    20 pelo Tab  fecha   0 sem nome  0 sem papel  0 nome vazio  PASSOU
  Galeria        49 focáveis    49 pelo Tab  fecha   0 sem nome  0 sem papel  0 nome vazio  PASSOU
  Veredito: PASSOU
```

O **portão** é do predecessor (`teclado.nome_vazio_de_sentido`, quatro motivos: eco do papel,
menos de três letras seguidas, repetido na aba, o valor do próprio controle), e ele já tinha
nomeado o grosso dos 34. Quando eu peguei o arnês faltavam **dois**, os dois pelo motivo *eco do
papel*: a `QListWidget` do topo do Resultado anunciada como `"Lista"` e a paleta de símbolos da
aba Texto, idem. Ambas agora dizem o que guardam (`strings.DIAGRAMAS_DA_PAGINA`, "Símbolos de
anotação").

**E o portão pegou uma coisa que eu mesmo tinha acabado de criar**, que é o melhor argumento a
favor dele: o botão `Varrer o livro` **dentro** do estado vazio da Galeria (item 14) tem o mesmo
rótulo do botão da barra da mesma aba, e o motivo *repetido na aba* reprovou os dois. O rótulo
desenhado continua igual -- é a proposta do §7, trazer a ação para dentro do vazio --, e o que
mudou é o `accessibleName`: "Varrer o livro para encher a galeria".

### 2. O rótulo do livro elidido — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\titulo_longo.py
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\sobreposicao.py
```

| | ciclo 1 | agora |
|---|---|---|
| `minimumSizeHint` com o nome de 149 caracteres | **1513**×890 | **1063×735** |
| `minimumSizeHint` com `1937 Kemeri.pdf` | 1243×890 | **1063×735** |
| os dois são iguais? | **não** | **sim, ao pixel** |
| controles fora da janela de 1920 | 1 | **0** |
| pares sobrepostos > 40 px² | 4 (o pior com 2.310 px²) | **1** — o `QLineEdit` interno do `QSpinBox`, que o §7 isenta |

O alvo do §7 era *"`minimumSizeHint` idêntico para qualquer nome de livro; zero controles fora da
janela; zero pares sobrepostos acima de 40 px² exceto o `QLineEdit` interno do `QSpinBox`"*. Os
três batem.

**E o `sobreposicao.py` pegou o estado vazio da Galeria**, que eu tinha feito como widget
sobreposto ao recorte: três pares novos, o maior com 17.640 px². O instrumento está certo e eu
estava errado -- ele conta pares que ocupam o mesmo pixel e não tem como distinguir "cobre de
propósito" de "colidiu". O recorte e o estado vazio agora dividem uma `QStackedLayout`: **um** dos
dois aparece, que é a verdade do que a aba faz.

`qt/rotulo.RotuloElidido` responde **zero** de `minimumSizeHint().width()`, elide no meio
(`ElideMiddle`, porque o fim do nome de um livro carrega o ano e a edição) e põe o nome inteiro na
dica. O `sizeHint` mede o **texto inteiro** e não o desenhado, com teto em
`LARGURA_DESEJADA = 130` -- medir o desenhado é um laço que encolhe o rótulo a cada passada, e
foi medido: o bloco saía com 90 px, 11 deles de rótulo.

**O rótulo da barra não era o único.** Depois de consertá-lo o `minimumSizeHint` continuava em
1513: a zona do documento no **rodapé** escreve `<livro> · p. 121 de 289 · …` e pedia **996 px**
sozinha. Ela é um `RotuloElidido` agora, e `Rodape.documento()` devolve `texto_inteiro`, que é o
que o teste pergunta.

### 3. A dica do estado vazio da aba Texto — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py dica
```

| largura da janela | ciclo 1 | agora |
|---|---|---|
| 1920 | ok | ok |
| 1366 | **cortada em 77 px** | ok |
| 1280 | **cortada em 77 px** | ok |
| 1063 (o piso) | cortada | ok, a frase quebra em duas linhas |

`placeholderText` não elide **nem quebra**, que era a causa. Ela virou `qt/vazio.EstadoVazio`,
sobreposto ao editor: um `QLabel` com `setWordWrap(True)`, mais o título e o botão `Ler folha`.
Ele some no primeiro caractere, então continua fora da exportação -- que era a razão de o ciclo 1
ter escolhido `placeholderText`, e ela continua valendo.

### 4. A janela cabe em 1366×768 — **fechado com ressalva**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\casos_ruins.py classica
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\casos_ruins.py foco
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py borda
```

| | ciclo 1 | agora |
|---|---|---|
| `minimumSizeHint` (clara) | 1243×890 | **1063×735** |
| `minimumSizeHint` (escura) | 1243×890 | **1063×769** |
| 1366×768 | **RECUSOU** (ficava 1366×890) | **OK nas duas peles** |
| controles abaixo de y=730 numa janela de 1366×768 | 13 % a 37 % por aba | **1 por aba: 1,9 % a 3,6 %** |

A causa estava isolada pelo crítico e era mesmo aquela linha: `setFixedSize(420, 420)` no recorte
da Galeria. Ele virou `qt/rotulo.RecorteElastico`, quadrado entre
`galeria_declarada.LADO_MINIMO_DO_RECORTE = 240` e `BOARD_VIEW_SIZE = 420`, com
`heightForWidth` e reescala a partir do **original** (reescalar o já reescalado perde definição a
cada gesto). O argumento original -- *"a galeria é para percorrer, e um tamanho que muda a cada
diagrama faria a imagem pular"* -- continua cumprido: o lado muda com a **janela**, nunca com o
item.

E `janela.LARGURA_MINIMA_DAS_ABAS` era `720` **cravado**, com um docstring dizendo que ele era a
soma de `galeria_declarada.LARGURA_MINIMA_DA_GALERIA`. Era, em 2026; deixou de ser no minuto em
que o recorte encolheu. Agora ele **é** a soma, e o piso caiu de 1243 para 1063 px de largura.

**As duas ressalvas, ditas com o número:**

1. O alvo do §7 era `minimumSizeHint() ≤ 1024×700`. Cheguei a **1063×735** (clara) e **1063×769**
   (escura) — **39 px de largura e 35 a 69 px de altura acima do alvo**. O que sobra é a coluna
   `Cabeçalhos do PGN` da Galeria: 516 px de altura em dez campos empilhados, e ela é a aba mais
   exigente das seis. Baixar isso é redesenhar aquela coluna, e não mexer numa constante.
2. Na pele escura o **`minimumSizeHint` diz 769**, um pixel acima de 768, e mesmo assim
   `resize(1366, 768)` **fica** em 1366×768 -- é a diferença entre o tamanho que o Qt *sugere* e o
   que ele *impõe*, e o que a pessoa vive é o segundo. `casos_ruins.py` afirma o segundo, e ele
   diz `OK` nas duas peles. Registro os dois números para ninguém ter de descobrir isso de novo.
3. **O "1 controle por aba" abaixo de y=730 é o rodapé**, que é onde ele deve estar numa janela
   de 768 px: a régua de 730 px do §7 supõe barra de tarefas, e a janela de 768 px desenha o
   rodapé entre 740 e 768. Não é um controle inalcançável; é o rodapé no rodapé.

### 5. O `csv` fora das duas threads de interface — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio --pdf "...\1937 Kemeri.pdf"
```

| operação | ciclo 1 (execuções) | agora (execuções) |
|---|---|---|
| aba Dataset, primeira vez | **1244 / 1447 / 1302** | **107,4 / 23,1 / 26,2** |
| abrir PDF | 250 (pilha: `csv.__next__`) | 255,8 / 271,7 / 275,0 (pilha: `path.resolve` da sala de estudo) |

**A aba Dataset caiu de 1.302 ms para 107 ms na execução fria**, e as duas execuções seguintes
ficam em 23-26 ms. E o que resta na fria **não é janela parada**: a pilha do pior aponta
`bloqueio.escoar`, o laço em que o próprio arnês bombeia eventos enquanto a thread de trabalho
corre -- ou seja, o tempo em que a aba está desenhando "Lendo o dataset" e respondendo ao
ponteiro, que é o oposto de congelar. `qt/painel_do_dataset._reler_agora`
manda `load_rows` para uma `qt/trabalho.Tarefa`; a aba fica cinza com a frase "Lendo o dataset" na
tabela enquanto isso, que é o que o §11.3 pede de uma operação longa e o que a versão síncrona não
tinha como oferecer.

A abertura do livro **não tem mais `csv` na pilha**: `qt/marcas.LeitorDeMarcas` lê o `labels.csv`
numa thread e descarta a resposta que chega depois de a pessoa trocar de livro. O que sobrou nos
~270 ms é a rasterização a 300 DPI (que o §7.1 do ciclo 1 já nomeava) mais um punhado de toques
de disco pequenos -- a pilha do pior agora é `estudo_arquivo.chave_de → Path.resolve`, que é o
`realpath` do sistema de arquivos, e não mais uma leitura de arquivo inteiro.

**Achei mais dois pela mesma régua, e consertei os dois** — os dois viraram a pior pilha do
"abrir PDF" assim que o `csv` saiu da frente:

- `painel_do_dataset.contagem_de_amostras` lia o `labels.csv` **inteiro** para responder o número
  do rótulo da aba, e `janela._atualizar_abas` a chama a cada livro, a cada página e a cada
  gravação. Passou a ser guardada por `(tamanho, mtime)` do arquivo — **249 ms medidos** naquela
  pilha antes.
- `painel_da_galeria._bases_atuais` fazia `glob("*.pgn")` na pasta das gigabases **três vezes por
  abertura de livro**, com a mesma resposta nas três — **283 ms medidos**. Passou a ser guardada
  pela `mtime` do diretório, que preserva exatamente a garantia da S-140: um `.pgn` a mais muda a
  `mtime`, e a varredura roda de novo.

**O que continua violando o piso de 16 ms, e é honesto dizer:** virar de página custa 174-200 ms,
e a pilha é `pdf_io.render_pdf_page → PyMuPDF`. É rasterização de verdade e ela **não** cabe num
`Tarefa` sem quebrar o contrato síncrono de `desenhar_pagina`, que o próprio §7 pediu para não
tocar. Fica para uma frente que possa mexer em `pdf_io`.

### 6. O arnês olha o pior — **fechado** (metade do predecessor)

O predecessor inverteu `viola`: `medir()` calcula `pior_ms = max(piores_ms)` e publica
`pior_ms_mediana`, `pior_ms_frio` e `pior_ms_por_execucao` ao lado. É o conserto certo.

**A tabela do terminal continuava imprimindo a mediana**, e essa metade era minha: a aba Dataset
saía escrita `14.6  VIOLA` na mesma linha -- um número que não explica o próprio veredito, que é
a definição do problema que este item veio corrigir. A coluna imprime `pior_ms` agora, com `frio`
e `mediana` ao lado, e o cabeçalho diz `a coluna e o PIOR de todas elas`.

### 7. Cancelamento nas duas operações longas — **fechado**

```
.venv\Scripts\python.exe -m caissa.ui.audit.progresso
```

```
  operacao                            total?  determ.?  cancel.?  onde
  DialogoDeTreino: barra fixa em i       NAO       NAO       NAO  qt/dialogos.py:668
  treino do modelo                       sim       sim       sim  qt/dialogos.py:740
  exportação para PGN                    sim       sim       sim  qt/exportador.py:139
  varredura do livro / busca por n       sim       sim       sim  qt/painel_da_galeria.py:506
  Exportando para … / Lendo o text       NAO       NAO       sim  qt/painel_de_texto.py:1163
  detecção de duplicatas                 sim       sim       sim  qt/painel_do_dataset.py:618

  Nenhum defeito bloqueante de progresso.
```

Partida: **1 defeito bloqueante, 2 operações sem cancelamento, 2 linhas do inventário chamadas
`"nome"`**. Chegada: **0, 0 e 0**.

- **Detecção de duplicatas.** O ciclo 1 registrava `cancellable=False` com o argumento de que
  *"`find_duplicate_groups` não tem por onde"*. O "por onde" estava no **argumento**: a função
  recebe um `Iterable` de rótulos, e um gerador que conta é a barra determinada, um gerador que
  levanta é o cancelamento. Nem uma linha de `audit.py` mudou -- e `audit.py` não é meu para
  mudar.
- **Exportação da aba Texto.** Cancelável, com o corte **entre** converter e escrever: cortar
  durante a escrita deixaria em disco o `.pdf` truncado que o próprio comentário de
  `loses_work=True` descreve.
- **Os dois `"nome"` do inventário.** Aqui o defeito era do **instrumento**, e é justo dizê-lo: as
  duas operações **têm** rótulo (`"varredura do livro"`, `"busca por nome na base"`,
  `"Exportando para …"`), passado por um ajudante `_registrar_ocupado(nome, ...)`. O que a
  varredura leu foi o nome do parâmetro. `progresso._nome_repassado` resolve o parâmetro contra os
  pontos de chamada do ajudante, no mesmo módulo.
- E `progresso._amarrado_ao_cancel` passou a reconhecer `cancellable=f is not None, cancel=f`, que
  é literalmente o que `busy.register` computa. A régua não afrouxou: exigir o `True` literal
  reprovava esse padrão (que **não pode** prometer sem entregar) e aprovava quem escrevesse
  `cancellable=True` com um `cancel` nulo em metade das chamadas.

### 8. A prancha de controles — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.amostrario --saida benchmarks\reports\ui
```

Oito imagens novas: `estados_{claro,escuro}_foco{0,1,2,3}.png`. Cada uma é a grade
**3 papéis × 5 estados** (repouso, sob o ponteiro, pressionado, com foco, desabilitado) mais a
linha do campo de texto, com **uma imagem por alvo de foco** — o Qt tem um foco só, e forjar três
anéis na mesma captura desenharia um estado que a janela nunca mostra.

O rótulo de cada célula bate com o que ela desenha, e é isso que faltava: o `amostrario.py` do
ciclo 1 rotulava uma célula "Com foco" e a linha seguinte chamava `setFocus()` **noutro widget**.
`WA_Hover` é o que faz a coluna "sob o ponteiro" repintar; sem ele ela sairia idêntica à de
repouso, que é o defeito do ciclo 1 com outra causa.

**As imagens são a prova do item 16**: em `estados_escuro_foco2.png` a coluna `pressionado` é
visivelmente mais escura que a de repouso nos dois papéis com ênfase.

### 9. A escala tipográfica — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py tipografia
```

| | ciclo 1 | agora |
|---|---|---|
| tamanhos distintos | **2** (11 e 12 px) | **3** (11, 12 e 13 px) — nas 12 combinações aba × pele |
| pesos distintos | **1** (400) | **2** (400 e 700) — nas 12 |
| combinações por aba | 2 | **3 a 4** |
| widgets com `TITULO` | **0** | 3 por aba (título de grupo, cabeçalho de coluna, título de estado vazio) |

O alvo do §7 era "3 tamanhos e 2 pesos presentes em cada aba" e "5-6 combinações"; cheguei a
**3 tamanhos e 2 pesos em todas as doze**, com 3 a 4 combinações. As combinações são menos que 5
porque a família monoespaçada (`DADO`) só aparece em três abas — e forçá-la nas outras seria
inventar dado onde não há.

**Dois mecanismos, e os dois são necessários.** `ui/folha_de_estilo._escala_tipografica` emite o
`QSS` de subcontrole (`QGroupBox::title`, `QHeaderView::section`, `QLabel[apoio="true"]`), que é o
que o Qt honra ao **pintar**; `qt/escala.aplicar_escala` é a varredura que muda `QWidget.font()`,
que é onde o censo do crítico olha. Um número que só melhora na fotografia é o defeito que este
ciclo veio corrigir, então os dois existem.

**O negrito não escorre**: fonte em Qt é herdada, e pôr `TITULO` num `QGroupBox` deixaria em
negrito os quinze controles dentro dele. A varredura declara `CORPO` em cada filho direto sem
papel próprio, explicitamente, que é o único jeito de a herança parar.

### 10. Uma ênfase por tela — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py enfases
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\sonda.py enfases
```

| aba | ciclo 1 | agora |
|---|---|---|
| Resultado | 3 | **1** |
| Estudo | 3 | **1** |
| Revisão | 3 | **1** |
| Texto | 2 | **1** |
| Dataset | 2 | **1** |
| Galeria | 2 | **1** |

A ênfase que sobrou é `ler_melhor` -- ler a página é o que esta janela faz, e ela está no painel
do PDF, que é visível nas seis abas. `anotar_pagina`, `salvar`, `estudo_do_diagrama` e
`"Corrigir agora"` viraram `NEUTRO`; as três primeiras no catálogo (`ui/comandos.py`), que é onde
o papel mora desde a S-324. As quatro continuam com tecla, com ícone e no primeiro lugar da fila.

`ui/estilos.conferir_tela` é onde a regra mora, e o instrumento a chama em vez de recontar --
`excesso_de_enfase=0` nas seis abas, na saída acima. Ela **devolve** os excessos em vez de
levantar, e é a diferença de contrato com `conferir_barra`: aquela é chamada na montagem, onde o
excesso é erro de programação e tem de doer; esta é chamada com a janela viva, e uma janela que se
recusa a abrir porque um botão está da cor errada troca um defeito de aparência por uma queda --
o contrato de degradação da S-53.

### 11. A barra do visor em blocos — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py refluxo
```

| largura da janela | filas (ciclo 1) | filas (agora) | trocam de fila vs 1920 |
|---|---|---|---|
| 1920 | 4 | **2** | — |
| 1600 | 5 | **2** | **0 / 12** |
| 1440 | 5 | **2** | **0 / 12** |
| 1366 | — | **2** | **0 / 12** |
| 1280 | 5 | **2** | **0 / 12** |
| 1243 | 6 | **2** | **0 / 12** |

Alvo do §7: ≤ 2 filas a 1243 px e ≤ 2 de 16 controles trocando de fila. **Duas filas em toda
largura de 1243 a 1920, e zero trocas.**

Quatro blocos nomeados, cada um um `QWidget` que reflui **inteiro**, com o traço de 1 px de
`qt/rotulo.separador` à esquerda de cada um a partir do segundo:

- **[Livro]** `Abrir PDF` · o rótulo elidido
- **[Reconhecer]** `OCR melhor diagrama` (a única ênfase) · três botões de ícone
- **[Navegar]** ◀ · o campo de página · `de 289` · ▶
- **[Zoom]** − · + · ajustar à largura · ajustar à página
- **[Exportação]** `Cancelar exportação`, **escondido** salvo durante a exportação

Saíram para os menus onde **já estavam declarados** em `ui/menu.MENUS`: `Exportar PDF → PGN` e
`Cancelar exportação` (Arquivo), `Marcar diagramas` e `Roda vira a página` (Ver), `Abrir no leitor
do sistema` (Arquivo). Nenhum comando perdeu alcance -- `ui/atalhos.py` mantém as teclas, e a
crítica é quem observou que a barra era "em boa medida uma segunda cópia" dos menus.

**O que isso custou, dito claramente:** oito dos doze controles da barra deixaram de escrever o
rótulo e passaram a desenhar só o ícone ou um glifo. O nome por extenso continua no
`accessibleName` (é o que um leitor de tela anuncia, e o portão do item 1 o cobra), na dica com a
tecla, e no menu. Foi essa troca que fez a conta de largura fechar: os rótulos por extenso somavam
367 px na barra mais estreita da janela, que tem 500 px.

`selecionar_area` é um **modo**, e trocava de rótulo para dizer em que estado estava (S-396). Dois
textos de larguras diferentes num botão da barra é largura da **barra**: ligar a seleção reflowava
a fila inteira. Ele é marcável agora, e o nome por extenso continua alternando.

### 12. A aba Estudo — **não fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py estudo
```

| | ciclo 1 | agora | alvo |
|---|---|---|---|
| botões da aba Estudo | 46 | **28** | ≤ 12 |
| filas | 4 | **4** | ≤ 2 |

**Não fiz este item, e o número caiu por efeito colateral.** Os 46 do ciclo 1 eram contados na
janela inteira (`j.findChildren`), e incluíam os do painel do PDF e do painel de campo; a minha
medida conta os do **painel da aba**, que são 28. Não é progresso: é outra régua.

O que o §7 pede -- colapsar `Colar / Abrir PGN / .md / .html / .rtf / Para o texto` num
`Exportar ▾` e mandar `Promover / Principal / Rebaixar / Apagar variante / Apagar daqui / Símbolo`
para o menu de contexto da árvore de lances -- é uma reorganização de `qt/painel_de_estudo.py`
(1.916 linhas) com um menu de contexto novo, e eu não tinha orçamento para fazê-la **e** deixar a
suíte verde. Fica declarado como não feito, com o número.

### 13. O tapete do tabuleiro — **fechado em parte**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py tapete
```

| | ciclo 1 | agora |
|---|---|---|
| tapete, % da janela de 1920×1080 | **10,9 %** | **1,31 %** (Resultado) / **1,48 %** (Estudo) |
| tabuleiro, % da mesma janela | 9,4 % | **14,69 %** / **19,02 %** |
| ocupação do painel, Resultado | 46,4 % | **58,3 %** |
| ocupação do painel, Estudo | 59,6 % | **80,8 %** |

**A relação inverteu**: a esteira inerte era maior que o objeto que ela existe para assentar, e
agora o tabuleiro é onze vezes maior que ela. Duas mudanças:

- `qt/tabuleiro._pintar_o_tapete` pinta o widget com a superfície do **painel** e só depois a
  esteira, numa faixa de `TAPETE_EM_VOLTA = 12` px em volta do tabuleiro. A esteira continua
  fazendo o que a S-147 pediu -- 11,03:1 nas coordenadas, e assentar em vez de flutuar --, mas
  deixou de ser **campo** e virou moldura.
- `MAX_DO_TABULEIRO` deixou de ser teto absoluto: ele é `max(560, min(largura, altura))`, o que o
  §7 pediu com essas palavras. É por isso que o Estudo saltou de 59,6 % para 80,8 %.

**O que não fechou, com o número:** o alvo era "ocupação ≥ 80 % em ambas as abas e a mesma nas
duas ± 3 pontos". Estudo chegou a **80,8 %** ✔; Resultado ficou em **58,3 %** ✘, e a distância
entre as duas é de **22,5 pontos**. A razão é geométrica e não é uma constante: o canvas do
Resultado é 933×560, largo e baixo, porque a paleta de peças divide o grupo com ele. Um quadrado
não passa de 58 % de um retângulo dessa proporção. Fechar isso é redesenhar aquele grupo.

### 14. Três estados vazios de verdade — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py vazio
```

Quatro, não três: `qt/vazio.EstadoVazio` — título (`TITULO`), frase (`AUXILIAR`, com quebra de
linha) e **o botão que resolve**, dentro do vazio.

| região | ciclo 1 | agora |
|---|---|---|
| Galeria (514,7 kpx) | 0,24 % de tinta, botão a 645 px, **duas** frases iguais a 320 px | "Nenhum diagrama ainda" + frase + `Varrer o livro`; a segunda frase **apagada** |
| Texto | 0,57 %, dica cortada em 77 px | "Nenhuma folha lida" + frase que quebra + `Ler folha` |
| Revisão (409,3 kpx) | **0,00 %** | "Nenhum item na fila" + frase + `Varrer o livro` (escondido enquanto há 27 itens na fila) |
| Resultado (a `QListWidget` de 1059×140 vazia com anel de foco) | o elemento mais destacado da tela era uma lista vazia | a lista **colapsa a zero** quando não há diagrama |
| Dataset (novo) | — | "Lendo o dataset" enquanto a leitura assíncrona corre |

O do Dataset **não estava na lista do §7**: ele é a contrapartida do item 5. Tirar `load_rows` da
thread da janela cria 1,3 s em que a tabela existe e está vazia, e uma tabela de dataset em branco
é uma afirmação sobre o `labels.csv`. Ele diz que a afirmação ainda não foi feita.

**Dois arranjos, e a diferença tem número.** Na Galeria o estado vazio e o recorte dividem uma
`QStackedLayout`: só um aparece. Nas outras três regiões (o editor da aba Texto, a tabela da
Revisão, a tabela do Dataset) ele é **sobreposto**, porque o widget de baixo é editável ou vai
encher sozinho, e ele instala um filtro de eventos no pai para acompanhá-lo. Sem esse filtro ele
desalinha na primeira mudança de janela -- medido: a frase do Dataset saía **cortada à direita** a
1280 px porque a geometria era a de 1920.

O arranjo empilhado veio de o `sobreposicao.py` do crítico ter contado a versão sobreposta da
Galeria como três colisões novas (a maior com 17.640 px²). O instrumento estava certo: ele conta
pares que ocupam o mesmo pixel, e não tem como distinguir intenção. Depois da pilha ele volta a
contar **uma** sobreposição na janela inteira, que é a do `QSpinBox` que o §7 isenta.

### 15. Uma margem esquerda — **fechado**

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\ui\medir_c2.py margens
```

| aba | ciclo 1 | agora |
|---|---|---|
| Resultado / Estudo / Revisão / Texto / Dataset / Galeria | 8, 9, 12 e 13 px | **10 px nas seis** |

Um valor, de `espaco.margem_da_aba()`. **É `folga()` (10 px) e não `moldura()` (14 px), e o número
foi buscado:** `moldura()` é a margem de um diálogo, e aplicada às seis abas ela somava 16 px de
altura por painel e punha o piso da pele "Foco" em **776 px** — oito acima dos 768 que o item 4
existe para caber. Está escrito no docstring da função, com a medição.

### 16, 17, 18 — a folha de estilo

- **16, `pressed` escurece** — **fechado pelo predecessor.** `ESCURECIMENTO_DO_PRESSIONADO = 0.20`
  e `letra_do_pressionado`, que reescolhe a letra contra a face já escurecida (na pele escura o
  destrutivo pressionado é `#bb544c`, e a letra de repouso caía a 4,03:1 sobre ele). Confirmado na
  imagem: `estados_escuro_foco2.png`. Eu só movi os dois hexadecimais para `ui/tokens.PRETO` /
  `BRANCO` e criei `tokens.escurecer`, porque `test_so_o_modulo_de_tokens_escreve_hexadecimal`
  reprovava o arquivo.
- **17, símbolo na caixa marcada** — **fechado.** `ui/icones.MARCAS` declara o visto e o traço com
  os mesmos `Poli` dos ícones da fita; `qt/tema.gravar_marcas` os desenha em PNG e a folha os põe
  em `QCheckBox::indicator:checked` e `:indeterminate`. A tinta é `TEXTO_SOBRE_ENFASE`, que é a
  letra que a folha já põe sobre a face primária e que `test_a_enfase_passa_no_piso` mantém acima
  de 4,5:1 — `sobre_superficie` **não** serve e foi medido: ela devolve `#5c5c5c` na pele escura, e
  isso sobre `#6ea8fe` some. Sem a Pillow ou sem a pasta, a folha volta ao preenchimento sólido do
  ciclo 1: aparência não derruba ferramenta. Ver `c2_caixas_claro.png` e `c2_caixas_escuro.png`.
  As marcas moram fora de `ICONES` porque aquela tabela é fechada contra `ui/comandos.CATALOGO`
  nos dois sentidos, e uma marca de indicador não é comando nenhum.
- **18, raio de canto** — **fechado pelo predecessor.** `RAIO_NA_BASE = 4`, com piso 3, escalando
  com a fonte. Deixou de ser `espaco.minima()`: raio de canto não é folga.

---

## §3 — O que não fechou, num lugar só

| item | alvo | onde parou | por quê |
|---|---|---|---|
| 4 | `minimumSizeHint ≤ 1024×700` | **1063×735** / **1063×769** | a coluna de headers da Galeria pede 516 px de altura; baixar é redesenhá-la |
| 12 | ≤ 12 botões e ≤ 2 filas na aba Estudo | **28 botões, 4 filas** | não feito: é reorganizar 1.916 linhas e criar um menu de contexto |
| 13 | ocupação ≥ 80 % nas duas abas, ± 3 pontos | **80,8 %** e **58,3 %** | o canvas do Resultado é 933×560; um quadrado não passa de 58 % dele |
| 5 (parcial) | nenhuma operação acima de 16 ms na execução fria | virar de página: **174-200 ms**; abrir livro: **~270 ms** | é `PyMuPDF` de verdade mais `realpath`, e `pdf_io` não é desta frente |

---

## §4 — As suítes

### A nossa

```
.venv\Scripts\python.exe -m pytest tests -q
```

| | antes | depois |
|---|---|---|
| | 2910 passaram, 1 pulado, 0 falharam | **2912 passaram, 1 pulado, 0 falharam** (642 s) |

Os dois a mais não são meus — não acrescentei teste à suíte da suíte; eles vêm da frente que
trabalha em `src/caissa/typeset/` ao mesmo tempo. **Zero regressões.** Os 83 testes de
`tests/unit/ui/` continuam passando, incluindo o de arquitetura (ADR-0009).

### A do tronco

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q
```

| | antes | depois |
|---|---|---|
| | 4409 passaram, 3 falharam | **4409 passaram, 2 pulados, 3 falharam** (258 s) |

**Empatado no passa e empatado no falha, com todas as mudanças em disco.**

**As 3 falhas de partida não são desta frente** e continuam iguais: `test_docs` (a árvore do
README sem `desenho_de_diagrama.py` e `pdf_substituicao.py`), `test_editor_model` (quatro módulos
de `ui/` fora de `SEM_TKINTER`) e `test_strings` (acentos em `biblioteca.py` e `substituicao.py`).
Os cinco arquivos são de outras frentes.

**Vinte e oito testes do tronco falharam por causa das minhas mudanças, e os vinte e oito estão
atualizados** — nenhum apagado, nenhum afrouxado; cada um passou a afirmar o contrato novo, com o
motivo escrito no docstring. Os que mudaram de asserção:

| teste | o que ele afirmava | o que ele afirma agora |
|---|---|---|
| `test_qt_painel_da_galeria.test_o_recorte_tem_o_lado_declarado` | lado **fixo** em 420 | lado **entre** 240 e 420, e quadrado — o §7 mandou atualizá-lo por nome |
| `test_qt_painel_da_galeria.test_o_estado_vazio_diz_o_que_falta_fazer` | a frase por cima do recorte | título + frase + botão do `EstadoVazio` |
| `test_qt_painel_do_pdf` (7) | o par exportar/cancelar permanente, o rótulo do modo, `btn_leitor` | o bloco de exportação contextual, o botão marcável, o nome acessível |
| `test_qt_painel_do_dataset` (10) | a leitura síncrona no `showEvent` | a mesma leitura, esperada por `aguardar_leitura()` |
| `test_ui_comandos.test_edicao_continua_com_um_primario` | um primário **por grupo** | um primário **na tela inteira** (renomeado) |
| `test_busy.SEM_REGISTRO` | as três threads que não registram | as cinco, com o motivo de cada uma das duas novas |
| `test_packaging.LIMITE` | `qt/janela.py` ≤ 1863 linhas | ≤ **1882**, com as 19 linhas justificadas item a item — é o que a própria catraca pede de quem sobe o número |
| `docs/ARCHITECTURE.md` | "Doze threads rodam fora" | "Catorze", com as duas novas nomeadas |

### §4.1 — A linha final, literal

```
3 failed, 4409 passed, 2 skipped, 28 warnings, 4301 subtests passed in 257.96s (0:04:17)
```

```
FAILED tests/test_docs.py::NumerosVivosTests::test_a_arvore_do_README_lista_todo_modulo_do_pacote
FAILED tests/test_editor_model.py::SemTkinterTests::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter
FAILED tests/test_strings.py::AccentTests::test_no_ui_string_uses_an_unaccented_portuguese_word
```

As três são as três de partida, sobre os mesmos cinco arquivos de outras frentes
(`desenho_de_diagrama.py`, `pdf_substituicao.py`, `biblioteca.py`, `cortina.py`,
`selecao_de_area.py`, `substituicao.py`). Nenhuma é minha, e nenhuma mudou de forma.

---

## §5 — Os portões que já estavam bons, reverificados

O §6 da crítica listou o que não podia quebrar. Rodei os três:

```
.venv\Scripts\python.exe -m caissa.ui.audit.contraste
```

```
  claro     287 pares   213 sob portão    0 reprovados  PASSOU
           menor folga: 3.27:1 contra piso 3.0 em marcação PROBLEMA sobre a casa escura
  escuro    287 pares   213 sob portão    0 reprovados  PASSOU
           menor folga: 3.03:1 contra piso 3.0 em QScrollBar::handle sobre QScrollBar
  Veredito: PASSOU
```

**287 pares e 213 sob portão**, contra 286 e 212 do ciclo 1: o par a mais é a marca do indicador
contra a face dele, que é a checagem de 1.4.1 que o item 17 pediu para acrescentar. Zero
reprovados nas duas peles, e o checador continua resolvendo a cascata do `QSS` em vez de ler uma
lista escrita à mão.

**ADR-0009**: `tests/unit/ui/` continua com 83 testes verdes num venv sem binding de Qt, e o teste
de arquitetura continua afirmando zero importação de toolkit nos módulos de `ui/`. Os quatro
módulos que eu criei são todos de `qt/` (`escala.py`, `marcas.py`, `rotulo.py`, `vazio.py`); as
decisões que eles executam moram em `ui/tipografia.PAPEL_POR_CLASSE`,
`ui/galeria_declarada.LADO_MINIMO_DO_RECORTE`, `ui/strings` e `ui/espaco.margem_da_aba`.

**FPS**, e a medição foi feita duas vezes de propósito:

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.quadros --pdf "...\1937 Kemeri.pdf"
```

| execução | pan | zoom | juntos |
|---|---|---|---|
| com a suíte do tronco correndo em paralelo | 395,3 | **50,6 REPROVOU** | 67,5 |
| com a máquina ociosa | **597,2** | **68,0** | **92,7** (execuções: 92,7 / 93,3 / 87,6) |

Publico as duas porque a primeira quase entrou neste relatório como regressão. Com a máquina
ociosa os três gestos passam, e o número conjunto (**92,7 fps @ p95**) fica **acima** dos 86,9 que
o crítico mediu e bem acima dos 78,0 que o ciclo 1 publicou. A lição é do instrumento e não do
produto: `quadros.py` mede tempo de parede e não tem como saber que outro processo está usando o
disco, então o número dele só vale com a máquina parada — e vale a pena ele dizer isso.

---

## §6 — Onde estão os artefatos

| o quê | onde |
|---|---|
| 36 capturas: 6 abas × 2 peles × 1920×1080, 1366×768, 1280×800 | `benchmarks/reports/ui/c2/c2_{claro,escuro}_{larg}x{alt}_{aba}.png` |
| a prancha papel × estado, 8 imagens | `benchmarks/reports/ui/estados_{claro,escuro}_foco{0..3}.png` |
| o amostrário de controles | `benchmarks/reports/ui/amostrario_{claro,escuro}.png` |
| as caixas de seleção, cinco estados | `benchmarks/reports/ui/c2_caixas_{claro,escuro}.png` |
| o instrumento deste ciclo | `benchmarks/reports/ui/medir_c2.py` |
| as capturas do ciclo 1, para comparar | `benchmarks/reports/ui/antes_*.png` e `depois_*.png` |
| os relatórios dos portões | `benchmarks/reports/ui/{teclado,contraste,progresso}.json`, `bloqueio_*.json`, `fps_*.json` |

**Olhei as 36 capturas, uma a uma**, e três defeitos saíram delas e não de nenhum instrumento:

1. a `QListWidget` vazia do Resultado ainda aparecia na abertura (o `setVisible(False)` estava
   só na repovoação e não na construção);
2. a Galeria ficou com **três** frases dizendo a mesma coisa depois de eu acrescentar o estado
   vazio — `lbl_posicao` some agora quando não há diagrama;
3. a frase do estado vazio do Dataset saía cortada à direita a 1280 px, que foi o que levou o
   `EstadoVazio` a instalar o filtro de eventos no pai.

---

## §7 — Duas coisas que eu quebrei e consertei, ditas porque o próximo ciclo herda o hábito

1. **Escrevi 1.486 `CR` soltos em `qt/painel_de_texto.py`**, e só descobri porque o inventário
   de progresso passou a apontar a **linha 2289** de um arquivo de **1.433 linhas**. A causa é
   uma armadilha da biblioteca padrão no Windows: `read_bytes()` preserva o par CR+LF, e o
   `write_text()` que vem depois traduz cada LF para CR+LF **outra vez** -- cada linha ganha um
   `CR` a mais. O Python continua analisando o arquivo (um `CR` sozinho é fim de linha válido) e a
   suíte continua verde, então nada acusa. O arquivo foi normalizado, `ruff check src/ tests/`
   passa, e o número de linha do inventário voltou ao lugar (1171).

   **A regra para quem editar arquivo por script neste repositório:** ou `read_bytes` e
   `write_bytes` nos dois lados, ou `read_text` e `write_text` nos dois -- nunca um de cada.

2. **O estado vazio da Galeria nasceu sobreposto** e virou três colisões novas no
   `sobreposicao.py`, a maior com 17.640 px². Ele é uma `QStackedLayout` agora.

Os dois têm a mesma forma: eu confiei no que a tela mostrava, e o instrumento discordou. Nos
dois casos o instrumento tinha razão -- e nos dois casos ele só falou porque alguém o rodou
depois da mudança, e não antes.

**Por que um segundo instrumento** (`medir_c2.py`) e não só o `sonda.py` do crítico: três das
sondas dele comparam `text()` literal, e oito dos doze controles da barra do visor deixaram de
escrever rótulo. Uma medição que passa porque o rótulo sumiu não mede nada. `medir_c2.py`
identifica os controles por `accessibleName`. O `sonda.py` continua rodando e continua no
relatório — ele é a régua de fora, e é dele que saem os números de ênfase e de tipografia acima.
