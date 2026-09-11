# F9 — Crítica adversarial, ciclo 5

```
VEREDITO: REPROVADO
CICLO: 5
FRENTE: F9 (Interface)
```

---

## Nota de procedimento

Continua não havendo conjunto cego para a F9 nesta máquina. A carta §2.1 segue substituída, como
nos ciclos 1 e 3, por um **julgamento itemizado dos nove critérios** (§3), cada um com a medida
que o sustenta.

**Todos os números deste documento são meus.** Olhei as **36 capturas** de
`benchmarks\reports\ui\c4\`, uma por uma, com a ferramenta de leitura de imagem. Rodei os seis
portões da carta §6 (contraste, teclado, progresso, bloqueio ×3, quadros ×3, sobreposição), a
suíte do tronco **duas vezes inteiras**, a suíte de fronteira, e **cinco dos sete instrumentos do
crítico do ciclo 3** (`quem_chama`, `qual_thread`, `detalhes`, `colapso`, `medidas_c3`) mais o
`sobreposicao.py` do ciclo 1. Escrevi seis instrumentos novos em
`benchmarks\reports\critique\ui\c5\` — `c5_tipos.py`, `c5_fonte.py`, `c5_peso.py`, `c5_casos.py`,
`c5_regioes.py`, `c5_vazios.py`, `c5_janela400.py` — porque três perguntas da Fase 3 não tinham
instrumento: *o peso 600 chega ao pixel?*, *qual é o maior vazio exato de cada painel?* e *a
janela de 400 ms fechou mesmo?*

**Divulgação minha, pela mesma regra que aplico ao construtor.** Rodei
`python -m caissa.ui.audit.contraste` sem `--saida` e **sobrescrevi
`benchmarks\reports\ui\contraste.json`**, que é um nome de arquivo fixo (`contraste.py:931`), não
carimbado com data. O arquivo tem os mesmos 184.621 bytes e os mesmos 287/213/0 de antes; o único
campo que mudou foi `quando`. Nada de evidência se perdeu, e o erro foi meu: eu devia ter olhado o
caminho antes, que é exatamente o que a ordem de serviço me mandou fazer. Daí em diante redirecionei
tudo para `--saida benchmarks\reports\critique\ui\c5`. **`teclado.json` tem o mesmo defeito de nome
fixo** e não foi tocado por mim.

Conferi ao fim da sessão, por `mtime`, **todo** arquivo fora da minha pasta de rascunho que mudou:
são **três**, e só três — `benchmarks\reports\ui\contraste.json` (sobrescrito, acima),
`benchmarks\reports\ui\progresso_20260908_045624.json` (arquivo **novo**, carimbado com a data,
não sobrescreveu nada) e este documento.

**Placar honesto:** verifico **nove das nove alegações** do construtor com número próprio, e os
**três bloqueantes do ciclo 3 estão genuinamente fechados** — verifiquei os três com os
instrumentos do próprio crítico que os levantou, e não com os do construtor. A suíte do tronco é
**estável em duas execuções completas**, sem `access violation`. Reprovo por **um** defeito novo,
que não é de desenho: um par de contraste **abaixo de WCAG AA no pixel** cujo portão publica
**1,79× o valor renderizado**. É meia linha de folha de estilo e uma linha de arnês.

---

## §1 — As 14 capturas destruídas: a divulgação foi tratada corretamente

**Sim, e sem ressalva.** Confiro os fatos:

| arquivo | dimensão real | dimensão que o nome anuncia | mtime |
|---|---|---|---|
| `c1_{claro,escuro}_1024x768_{6 abas}.png` (12) | **1066×768** / **1066×769** | 1024×768 | **08/09 01:26** |
| `c1_{claro,escuro}_pagina289.png` (2) | 1920×1080 | — | **08/09 01:26** |
| `c1_estados_*.png` (7) | 1180×240 | — | 07/09 16:50–16:52 |
| `c1_titulo_longo_*.png` (3) | 1243/1440/1920 | — | **07/09 21:53** |

As 14 são do ciclo 4 com nome do ciclo 1, como declarado. **Trato as 14 como evidência não
confiável** e não usei nenhuma delas. A causa está no instrumento:
`casos_ruins.py:16` crava `SAIDA = Path(r"...\benchmarks\reports\critique\ui")` e grava com prefixo
`c1_` — não aceita `--saida`, não carimba a data, não faz cópia.

**Duas coisas que o construtor não podia saber e eu registro:**

1. **O mesmo defeito já tinha destruído três arquivos antes, e ninguém disse nada.**
   `titulo_longo.py:10` e `estados.py:15` cravam a **mesma** pasta e o **mesmo** prefixo `c1_`. As
   `c1_titulo_longo_{1243,1440,1920}.png` têm mtime **21:53 de 07/09** — **depois** do
   `F9_REPORT_C2.md` (21:37) e **antes** da `F9_CRITIQUE_C3.md` (22:10), isto é, dentro da janela
   de trabalho do ciclo 3. Elas **não são do ciclo 1** tampouco, e ninguém disse nada. O ciclo 4
   perdeu 14 e **avisou**; três outras se perderam um ciclo antes **em silêncio**. A divulgação do
   construtor não é só correta — é o único registro que existe do problema.
2. **O defeito é da família dos arnesses, não do `casos_ruins.py`.** `contraste.json` e
   `teclado.json` também são nomes fixos que sobrescrevem (e eu caí num deles, §Nota).
   `bloqueio_*.json`, `fps_*.json` e `progresso_*.json` carimbam a data e estão certos.

**Conduta:** o construtor não renomeou nem apagou nada (certo — o §8 do ciclo 1 cita os nomes),
publicou a lista completa dos 14, publicou a hora, publicou que não há cópia, publicou a causa e
publicou o aviso para o próximo ciclo. É exatamente o que a carta §6 pede. **Não é falta.**

---

## §2 — Reverificação dos três bloqueantes do ciclo 3

### Bloqueante 1 — a leitura do `labels.csv` na virada de página: **FECHADO**

Medido com **os dois instrumentos do crítico que o levantaram**, sem tocá-los:

```
quem_chama.py   → virar p.41  113.0 ms; 0 leituras completas do labels.csv
                  virar p.121 108.1 ms; 0 leituras completas do labels.csv
qual_thread.py  → virar p.41 / p.42 / p.121: "(nenhuma chamada de labels/pdf_io registrada)"
                  abrir PDF: 23.3 ms, 40.820 chamadas de labels._clean  [Dummy-1]
```

Eram **108.620 chamadas de `labels._clean` na `MainThread` por virada** e **1 leitura completa por
virada**. Agora são **zero** das duas; o único trabalho de `labels` que sobrou está numa **thread
de trabalho** (`Dummy-1`), na abertura do livro, e custa 23,3 ms lá.

O `c4_custo_aviso.py` reproduz na minha máquina:

```
virada COM o aviso de treino: [95.1, 99.8, 93.3, 90.4, 119.2, 103.8] -> mediana 97.5 ms
virada SEM o aviso de treino: [105.7, 92.4, 97.4, 91.8, 106.8, 112.2] -> mediana 101.5 ms
CUSTO do aviso: -4.1 ms          ALVO <= 116 ms -> PASSA
```

**Alvo do §7.1 do ciclo 3: ≤ 116 ms. Medido: 97,5 ms pelo script adaptado, 98,8–101,2 ms pelo
arnês (medianas de 3 execuções, máquina ociosa). Era 171,4 ms. PASSA.**

### A adaptação do `custo_aviso.py` é **fiel, e mede mais do que o original — não menos**

A ordem de serviço mandou adjudicar isto. Adjudico:

| | o que é neutralizado | o que fica de fora da conta |
|---|---|---|
| `c3/custo_aviso.py` | `LabelStore.read()` → `[]` | só a **leitura do arquivo** |
| `c4/c4_custo_aviso.py` | `marcas.paginas_com_amostra_de_treino` → `{}` | a leitura **mais** o cálculo **mais** a consulta à memoização |

O braço "sem" do construtor é **estritamente mais barato** que o do crítico: ele apaga a função
inteira, não só o `read()`. Logo a diferença `com − sem` que ele publica é um **limite superior**
do resíduo, e ela sai em **−4,1 ms** (a minha) e **−9,5 ms** (a dele) — zero dentro do ruído nas
duas. **Não mede algo mais fácil; mede algo mais difícil e passa assim mesmo.**

Uma ressalva que é do **desenho original do crítico** e o construtor herdou: os dois braços usam
**páginas diferentes** (`[40,41,120,60,61,62]` contra `[80,81,82,83,84,85]`). Páginas de custo de
rasterização diferente entram nas duas medianas, e por isso um efeito de ±10 ms **não é
resolvível** por este desenho. Isso não enfraquece a conclusão, porque a alegação central — *zero
leituras por virada* — é provada por um instrumento de **contagem** (`quem_chama`/`qual_thread`),
não por um de relógio.

### Bloqueante 2 — barra permanente, leituras não registradas, portão cego: **FECHADO**

Três metades, três medições:

**(a) O portão lista 8 e vê as threads.** `caissa.ui.audit.progresso`, minha execução:

```
(8 indicadores de progresso)
Operacoes de fundo em qt/ (13): 10 REGISTRADA, 3 DECLARADA, 0 INVISIVEL
Nenhum defeito bloqueante de progresso.
```

Idêntico ao publicado. As três DECLARADAS (`janela._rodar`, `painel_de_estudo.analyse`,
`trabalho._comecar`) têm motivo escrito em `ui/busy.FORA_DO_REGISTRO`, e o portão **lê a tabela do
produto por AST** em vez de guardar uma cópia — isso é a correção certa do defeito de instrumento
do ciclo 3.

**(b) A barra some quando não há nada.** `detalhes.py`, o instrumento do crítico, janela ociosa:

```
visivel=False  x=1712 y=1051  120x26  faixa=0..100 valor=0 texto_visivel=False
botao Cancelar: habilitado=False
```

Era `visivel=True, 0/100, texto_visivel=False`, **permanente nas 36 capturas do c2**.

**(c) As 36 capturas não se contradizem — e eu conto o placar que o construtor não contou.**
Censo de pixel do rodapé nas 36 (`azul` = pixels de matiz 200–260° com saturação > 0,35 na faixa do
rodapé; `Cancelar` = tinta na caixa dos 88 px finais):

| grupo | n | pixels azuis | tinta na zona da barra | tinta no `Cancelar` |
|---|---|---|---|---|
| **ociosas** (`Página 121 pronta.`) | **8** | **0** | 366–370 | 111–117 |
| **ocupadas** (`Lendo o dataset…`) | **28** | 1404–1428 | 1417–1543 | 242–247 |

**Bimodal, sem uma única exceção: 0 de 36 se contradizem.** As 8 ociosas são
`c4_{claro,escuro}_1280x800_{resultado,estudo,revisao,texto}`.

**(d) A janela de 400 ms fechou, e eu medi com o relógio afastado** (`c5_janela400.py`). Empurrei
**todos os relógios do rodapé para 10 s** — se fosse o tique a acender a barra, o teste falharia —
e registrei uma operação **de uma thread de trabalho**, que é o caminho real:

```
A. ocioso                          barra.visivel=False  faixa=0..100  Cancelar=False
C. registrado de thread, 1 ciclo   barra.visivel=True   faixa=0..0    Cancelar=True    (2.9 ms)
E. depois de release(), 1 ciclo    barra.visivel=False  faixa=0..100  Cancelar=False   (13.0 ms)
F. release() depois de deleteLater() da janela:  sem queda
```

**2,9 ms, não 400.** E o `F` é o `access violation` do ciclo 4: a guarda `weakref` +
`sip.isdeleted` segura.

### Bloqueante 3 — a prancha de estados desenhava `hover` igual a repouso: **FECHADO**

Recalculei o ΔRGB **a partir dos PNGs**, sem confiar no manifesto, nas 8 pranchas × 4 papéis:

| pele | NEUTRO | PRIMARIO | DESTRUTIVO | campo |
|---|---|---|---|---|
| claro (foco0..3) | **25** (91,4 % dos pixels) | **36** (99,4 %) | **26** (99,6 %) | 0 (0,0 %) |
| escuro (foco0..3) | **15** (91,3 %) | **27** (99,7 %) | **30** (99,7 %) | 0 (0,0 %) |

**Divergências entre o manifesto e o pixel: 0 em 32 comparações.** Era ΔRGB **zero** nas 8
pranchas, nos 4 papéis. E a isenção do `campo` é verdade do produto, conferida por mim em
`ui/folha_de_estilo.py:439-452`: o bloco `campos` (dez seletores) declara `:focus` e `:disabled` e
**nenhum** `:hover`; `QComboBox` está em `controles_com_face` e **tem** `:hover`.

---

## §3 — Os nove critérios: isto sobrevive ao lado do Affinity Publisher?

### 1. Hierarquia visual — **SOBREVIVE COM RESSALVA**

`excesso_de_enfase = 0`: censo de `papel` nos botões visíveis, seis abas, 1920 **e** 1366,
pele clássica:

```
Resultado 1 primário 1 destrutivo    Estudo 1/3    Revisão 1/1
Texto     1/1                        Dataset 1/3   Galeria 1/2
```

E os cinco rebaixados ganharam tecla — medido em `ui/atalhos.por_acao`: `corrigir_agora`
`Ctrl+Shift+N`, `anotar_pagina` `Ctrl+G`, `estudo_do_diagrama` `Ctrl+E`, `ler_melhor` `Ctrl+D`,
`salvar` `Ctrl+S`. **5 de 5** (era 1 de 5); 25 ações com tecla, contra 21.

**A ressalva é a mesma do ciclo 3 e o construtor a declara:** a única primária da janela continua
sendo `OCR melhor diagrama`, e ela está na barra do visor — **6 de 6 abas sem ação primária
própria**. Na Revisão, `Corrigir agora` continua pixel a pixel igual a `Marcar revisado`, `Pular`,
`Reabrir` e `Próximo pendente`. Isso agora custa menos, porque a tecla existe; não custa nada.

### 2. Ritmo espacial — **SOBREVIVE**

Item 11 do §7 do ciclo 3 fechado e conferido por mim com `detalhes.py`: os cinco botões da coluna
"Cabeçalhos do PGN" em **x = 825, largura 218, valores distintos de x: [825]** — desalinho **0 px**
contra **63 px**. A barra do visor continua em **duas filas sem refluxo** de 1243 a 1920.

### 3. Alinhamento — **SOBREVIVE**

Nada regrediu. A margem esquerda única de 10 px do ciclo 3 continua, e a `QSplitter` principal
agora tem alça de **6 px** (era 3) com `childrenCollapsible=False`.

### 4. Densidade × vazio — **NÃO SOBREVIVE a 1920, e sobrevive abaixo disso**

Medi o **maior retângulo vazio exato** de cada painel — algoritmo do maior retângulo em histograma
sobre a máscara de blocos 4×4 sem tinta, não busca gulosa (`c5_vazios.py`). Alvo do §2.4:
nenhuma região acima de 200 kpx com menos de 2 % de tinta.

| aba | c2 claro 1920 | **c4 claro 1920** | c4 escuro 1920 | c4 claro 1366 | c4 claro 1280 |
|---|---|---|---|---|---|
| Texto | 423,4 kpx | **421,8** | 405,1 | 169,8 | 169,6 |
| Revisão | 396,7 | **391,0** | 357,8 | 20,6 | 19,3 |
| Dataset | 389,9 | **371,7** | 350,8 | 137,6 | 153,2 |
| Estudo | 244,4 | **268,3** ↑ | 255,3 | 87,0 | 21,6 |
| Galeria | 222,9 | **218,6** | 205,9 | 58,1 | 51,8 |
| Resultado | 223,0 | **202,7** | 195,0 | 87,6 | 81,1 |

**11 de 12 painéis a 1920 estouram os 200 kpx; 0 de 12 a 1366 e 0 de 12 a 1280.** A mediana da
variação c2→c4 a 1920 é **−1,7 %**, e a aba Estudo **piorou 9,8 %**. O trabalho de composição
deste ciclo é real no visor e no canvas, e **não mexeu no maior vazio de tela grande**. O construtor
declara isso no §4 e no §9 — é honesto, e continua sendo o critério que não passa.

**Item 13, com a minha régua** (`c5_regioes.py`, painel esquerdo, faixa vertical do tabuleiro):

| | c2 claro 1920 | c4 claro 1920 |
|---|---|---|
| vão entre tabuleiro e paleta | **203 px** = 111,9 kpx a 5,91 % | **16 px** = 8,8 kpx a 25,0 % |
| largura vazia na faixa do tabuleiro | 402 px de 1025 (**39,2 %**) | 305 px de 929 (**32,8 %**) |
| à direita da paleta | ~13 px | **289×552 = 159,5 kpx a 0,00 %** |
| ocupação do tabuleiro **no painel** | 551²/(1025×551) = 53,8 % | 552²/(929×552) = **59,4 %** |

**O vão fechou de verdade — 203 px para 16 px, uma ordem de grandeza.** Mas os **86,2 %** que o
relatório publica são a ocupação contra uma caixa que **termina na borda direita da paleta**, isto
é, uma caixa que exclui a emptiness que a mudança criou. Contra o **painel**, que é o que o olho
vê, a ocupação é **59,4 %** (claro) e **56,6 %** (escuro) a 1920, **51,5 %** a 1366. O construtor
declara os 203,3 kpx à direita da paleta no §2 e diz por que não os fechou; eu meço 159,5 kpx e
concordo com a explicação — o tabuleiro é limitado pela **altura**. O que não aceito é a régua:
**a emptiness mudou de lugar, não desapareceu, e o número de 86,2 % não conta isso.**

E o visor: **520 / 557 / 800 px** de largura de página a 1280 / 1366 / 1920 (`medidas_c3.py
pagina`), contra **366 px nas três** no c2. A 1920 a página ocupa **97,7 %** do viewport útil.
Este item está fechado sem ressalva, e é a maior conquista visual do ciclo.

### 5. Cor como sinal — **SOBREVIVE. Continua o melhor item da frente.**

Censo de matiz meu, restrito ao **cromo** (painel esquerdo, sem o visor), saturação > 0,25:

| captura | % do cromo em cor | famílias |
|---|---|---|
| `c2_claro_1920x1080_galeria` | 0,06 % | **210° apenas** |
| `c4_claro_1920x1080_galeria` | 0,06 % | **210° apenas** |
| `c4_escuro_1920x1080_galeria` | 0,06 % | 210° (+ 225° residual) |

Idêntico entre os ciclos e entre as peles: **um matiz, 0,06 % da superfície**. (Na tela inteira o
número sobe de 0,73 % para 2,09 %, e a diferença é **o documento** — a página do visor dobrou de
tamanho. Isso é conquista, não vazamento de cor.)

### 6. Tipografia da interface — **SOBREVIVE no número, com uma ressalva medida**

Reproduzi o censo do ciclo 3 (`QWidget.font()` sobre widgets visíveis) **e** acrescentei a régua
que faltava: `QFontInfo`, que diz o que o Qt **resolveu**, não o que o código **pediu**.

| aba × pele × tamanho (18 combinações) | maior combinação única |
|---|---|
| pior caso — Galeria, 1920, clássica | **69 de 107 = 64,5 %** |
| melhor caso — Estudo, 1920, foco | 54 de 107 = 50,5 % |

Galeria 1920, distribuição completa (**pedido idêntico ao resolvido, widget a widget**):

```
(12 px, 400) 69 (64,5 %)   (12 px, 600) 30 (28,0 %)   (11 px, 400) 5   (16 px, 700) 3
```

**Alvo do §7.6: ≤ 80 % numa única combinação. Medido: 64,5 %, e nenhuma das 18 combinações passa
de 64,5 %. Era 92,5 %. PASSA.** O construtor publicou 65,4 % (70 de 107); eu meço 69 — um widget de
diferença, dentro do ruído de "o que estava visível naquele instante".

**E o eixo novo chega ao pixel — mas com metade da força que as capturas mostram.** Rendi o mesmo
texto nos três papéis e diferenciei pixel a pixel (`c5_peso.py`):

| texto | CORPO→ACAO, no ambiente das capturas | CORPO→ACAO, na plataforma real | CORPO→TITULO (real) |
|---|---|---|---|
| `Varrer o livro` | +37,2 % de tinta | **+13,6 %** | +214,4 % |
| `Corrigir agora` | +37,0 % | **+5,4 %** | +198,8 % |
| `Copiar headers para todos` | +27,0 % | **+8,8 %** | +194,8 % |
| `Marcar revisado` | +31,6 % | **+13,2 %** | +199,5 % |

A causa está no §7, defeito 3: as capturas não são feitas na fonte do produto. **`TITULO` é inequívoco nas
duas (+195 % a +214 % de tinta); `ACAO`, que carrega 28 % dos widgets, é +5,4 % a +13,6 % de tinta
a 12 px na fonte que o usuário realmente vê.** O portão passa; o degrau que ele conta é mais fraco
do que as pranchas sugerem.

### 7. Controles — **SOBREVIVE**

O `hover` agora tem prova (§2, bloqueante 3): 91,3 %–99,7 % dos pixels da célula mudam, ΔRGB
15–36, nas 8 pranchas. `pressionado`, `foco` e `desabilitado` continuam distintos. Raio, cantos e
indicadores de marca não regrediram.

**Ressalva medida, e é nova:** os **sete botões só-de-ícone da barra do visor** vêm de grades
diferentes. Medi a caixa do glifo e a fração de tinta dentro dela na
`c4_claro_1920x1080_resultado.png`:

| botão | caixa do glifo | tinta/caixa |
|---|---|---|
| `ajustar à página` | 14×10 | **65,7 %** (sólido) |
| `×` (tirar a caixa) | **4×5** | 60,0 % — **é um caractere de texto, não um ícone** |
| `ajustar à largura` | 14×8 | 44,6 % |
| `ler_pagina` | 12×14 | 40,5 % |
| `zoom +` | 11×11 | 34,7 % |
| `zoom −` | 11×11 | 33,9 % |
| `tela cheia` | 12×12 | 30,6 % |

**Cinco grades ópticas, densidade de tinta de 30,6 % a 65,7 % (2,1×), traço fino e sólido lado a
lado, e um "ícone" de 4×5 px num botão de 26 px — 1/9 da massa visual do vizinho.** Carta §3.3,
*"ícones de origens diferentes misturados (peso, estilo, grade)"* e *"alinhamento óptico errado"*.
Está nas 36 capturas e nenhum dos quatro ciclos o nomeou.

### 8. Estados vazios — **NÃO SOBREVIVE, por uma frase**

A ressalva do ciclo 3 caiu: `detalhes.py` devolve **uma** afirmação de "nada varrido" na Galeria
(`'Nenhum diagrama ainda'`, y=362) com a sua explicação 28 px abaixo — eram duas a 302 px e três no
ciclo 1. Os estados vazios de Texto, Dataset e Galeria têm título, frase e **o botão que resolve
dentro do vazio**, e o texto da aba Texto se lê inteiro nas três larguras (0 widgets espremidos,
§8, item 9).

**Mas o estado vazio da aba principal manda o usuário apertar um botão que não existe.** Isto é o
§7, defeito 1, e é o achado de Fase 3 que considero mais sério depois do bloqueante.

### 9. A pele escura — **SOBREVIVE**

Projetada, não invertida: fundo `#1f2124`, superfície elevada `#26282b`, um azul dessaturado como
cinza de cromo, listras de tabela próprias, `pressionado` que escurece. Contraste 287/213/0 nas
duas peles. As duas ressalvas antigas continuam, medidas por mim:

- **A pele "Foco" entrega menos superfície de trabalho:** tabuleiro **552 px (claro) contra 526 px
  (escuro)** a 1920 — **−9,2 % de área** — e **318 contra 292** a 1366 — **−15,7 % de área**,
  exatamente o número do ciclo 3. A fila de quatro pílulas do topo custa 34 px de altura e o
  tabuleiro paga; a ocupação do canvas na pele escura a 1366 é **47,2 %** contra 51,5 % na clara.
- **Duas das quatro pílulas continuam duplicando botões visíveis na mesma tela**: `Aplicar a FEN
  digitada` e `Salvar a posição` aparecem nas pílulas **e** na fila de ações do painel, na mesma
  captura.

---

## §4 — Os portões, remedidos (carta §6)

| portão | relatório C4 | minha medição | veredito |
|---|---|---|---|
| Contraste WCAG AA | 287 / 213 / **0**; folga mín. 3,27:1 e 3,03:1 | **idêntico ao par**, nas duas peles | **CONFIRMADO no número, REFUTADO no método — bloqueante nº 1** |
| Teclado + nome + papel | 24+52+30+39+21+50 = **216**, 0 sem nome/papel/vazio | **idêntico**, seis abas `PASSOU` | **CONFIRMADO** |
| Progresso | 8 indicadores; 13 threads: 10/3/**0** | **idêntico** | **CONFIRMADO no produto, ver §5** |
| Cabe em 1366×768 | `minimumSizeHint` **1066×735** / 1066×769 | **1066×735**, 0 controles fora | **CONFIRMADO** |
| Nome de 149 chars | mesmo `minimumSizeHint`, 0 fora, 1 sobreposição | **1066×735** nos dois; **0 fora**; **1** par (987 px², o `QLineEdit` do `QSpinBox`, isento) | **CONFIRMADO** |
| fps ≥ 55 @ p95 | 85,4 · 87,6 · 88,8 → 87,6 | **88,0 · 93,4 · 91,1 → mediana 91,1**; pan 568–726, zoom 66,1–69,9 | **PASSA (66 % de folga)** |
| Nada bloqueia > 16 ms | 7 operações violam | **7 violam**; medianas de 3: abrir PDF **238,8**, p.41 **98,8**, p.42 **101,2**, p.121 **101,2**, rasterizar **71,7**, aba Dataset **17,8**, aba Galeria **20,0** | **REPROVA, e a causa é PyMuPDF** |
| Atribuição por família | virada 1,8–2,4 % desta frente | **1,5 % a 2,3 %** nas 12 medições (3 execuções × 4 operações) | **CONFIRMADO** |
| Suíte do tronco | `3 failed, 4418 passed … 249.24s` | **execução 1: `3 failed, 4419 passed, 2 skipped, 28 warnings, 4319 subtests passed in 273.70s`**<br>**execução 2: idêntica, `279.18s`** | **CONFIRMADO — e estável em duas execuções completas** |
| ADR-0009 | 110 passed | **`110 passed in 0.62s`** num venv sem binding (`find_spec` = `None` para os 6 bindings); varredura AST minha de **58** módulos de `ui/`: **0** imports de toolkit ou de `qt/` | **CONFIRMADO** |

**Sobre a suíte do tronco, que a ordem de serviço mandou verificar duas vezes:** rodei **duas
execuções completas, sequenciais, sem paralelismo**. As duas linhas finais são iguais campo a
campo e as três reprovações são as mesmas três, pelo nome
(`test_docs`, `test_editor_model`, `test_strings`). **Nenhum `Windows fatal exception` em nenhuma
das duas**, e o `c5_janela400.py` reproduz o caminho exato que derrubava o processo
(`release()` depois de `deleteLater()`) **sem queda**. Conto 4419 aprovados contra os 4418 do
relatório — **um teste a mais, nas duas execuções**. Rodei com `-p no:randomly` para que as duas
execuções fossem comparáveis entre si; a diferença de um caso contra o relatório é de ambiente
(um motor de OCR presente ou ausente muda a coleta), e não intermitência: as minhas duas
execuções concordam.

---

## §5 — Sabotagem do detector de "thread invisível"

A ordem de serviço mandou sabotá-lo. Copiei o `src/` do tronco para
`benchmarks\reports\critique\ui\c5\sabotado\`, plantei **seis** operações de fundo num módulo novo
de `qt/`, **nenhuma** registrada e **nenhuma** declarada em `FORA_DO_REGISTRO`, e rodei o portão
contra a cópia. **O tronco não foi tocado.**

| # | forma plantada | o portão diz |
|---|---|---|
| a | `threading.Thread(target=…)` | **INVISIVEL** ✔ (controle: o detector funciona) |
| b | `Thread(…)` via `from threading import Thread` | **não aparece** |
| c | `ThreadPoolExecutor(1).submit(…)` | **não aparece** |
| d | `threading.Timer(0, …)` | **não aparece** |
| e | `class _MinhaThread(threading.Thread)` + `_MinhaThread().start()` | **não aparece** |
| f | `threading.Thread(…)` numa função que chama `self._registrar_atalho_de_teclado()` | **REGISTRADA** ← falso positivo |

**1 de 6 detectada; 1 de 6 marcada como registrada sem registro nenhum; 4 de 6 invisíveis para o
detector de invisíveis.** A causa está escrita no código:
`progresso.py:351 FORMAS_DE_THREAD = ("threading.Thread", "Tarefa")` compara
`ast.unparse(no.func)` com duas grafias literais, e `progresso.py:397 _registra` aceita
**qualquer** chamada cujo nome contenha `register` ou `registrar` como prova de registro.
`tests/test_busy.py:63,85` usa **exatamente as mesmas duas regras** — o teste e o portão
compartilham o ponto cego.

**Sou justo com o alcance disto.** Varri `qt/`: hoje existem **exatamente duas** grafias
(`threading.Thread` e `Tarefa`), e a escolha está documentada em `test_busy.py:50` (*"Duas formas,
e as duas contam"*). Então o portão **cobre o código de hoje**, e o "0 invisíveis" do relatório é
verdade sobre o produto. O que não é verdade é a generalização: **uma thread nova escrita em
qualquer outra grafia passa pelo portão e pela suíte em silêncio**, que é a forma exata do defeito
que este detector foi construído para matar. **Não bloqueia; é o item 3 do §9.**

---

## §6 — Defeitos bloqueantes

### 1. O texto de dica do campo fica em **3,96:1** na pele clara — abaixo de WCAG AA — e o portão de contraste publica **7,08:1** para o mesmo par. O comentário logo acima da linha descreve este defeito e afirma tê-lo consertado.

**Onde:** `ui/folha_de_estilo.py:495-499`; `qt/tema.py:295-305`;
`caissa/ui/audit/contraste.py:657` e `:684-698`.

**O que o portão publica** (`contraste.json`, o meu e o do construtor, byte a byte iguais):

```json
{"onde": "QPalette.Active: PlaceholderText sobre Base",
 "frente": "#555555", "fundo": "#f8f9fb", "razao": 7.076941622370282,
 "piso": 4.5, "especie": "texto", "portao": true, "nota": ""}
```

**O que a janela desenha.** Aba Dataset, leitura do dataset **concluída**, campo de busca
**habilitado** — o estado permanente da aba —, medido no pixel do `grab()` do próprio widget:

| pele | campo | fundo | núcleo do glifo | razão |
|---|---|---|---|---|
| **clássica** | `Arquivo, FEN ou livro` | `rgb(248,249,251)` | `rgb(124,124,126)` | **3,96:1** ← abaixo de 4,5:1 |
| foco | `Arquivo, FEN ou livro` | `rgb(21,23,26)` | `rgb(128,129,131)` | 4,61:1 |

Nas 36 capturas, com o campo ainda desabilitado, os mesmos glifos dão **2,21:1** (claro) e
**2,88:1** (escuro) — abaixo até do piso de 3:1 —, e ali a WCAG 1.4.3 isenta por ser componente
inativo. **O caso acima não é isento: o campo está habilitado e é o estado normal da aba.**

**A causa, isolada.** `qt/tema.py:297-300` põe `PlaceholderText = TEXTO_SECUNDARIO` (`#555555`
claro, `#a7adb6` escuro) na `QPalette` da aplicação. O widget não recebe isso: sondei
`le.palette().color(Active, PlaceholderText)` na janela viva e ele devolve **`#000000` com
alpha 128** na pele clara e **`#e9eaec` com alpha 128** na escura — o Qt deriva a dica da cor de
texto da folha de estilo, a 50 % de alfa. `#000000` a 50 % sobre `#f8f9fb` = `rgb(124,124,126)`, que
é **exatamente** o que medi. Não é anti-aliasing: é a aritmética da composição.

**O portão não pode ver isso** porque `contraste.pares_da_paleta` resolve o papel pelo **token**
(`tokens.cor(papel, …)`, sempre opaco) e nunca compõe o alfa que o produto aplica. Ele publica
`#555555` sobre `#f8f9fb` = 7,08:1; a tela dá 3,96:1. **Fator 1,79× na direção que transforma uma
reprovação em aprovação.**

**E o código sabia.** `ui/folha_de_estilo.py:495-498`:

> *"**O texto de dica do campo é papel, e não um cinza qualquer.** Sem esta linha o Qt desenha o
> `placeholderText` com a cor do texto a 50% de alfa, que sobre o poço escuro cai abaixo do piso AA
> sem que nenhuma tabela de cor saiba."*

A linha que esse comentário introduz é:

```python
f"QLineEdit[echoMode=\"0\"] {{ selection-background-color: {selecao}; }}",
```

**`selection-background-color` é o realce da seleção. Não tem relação nenhuma com o
`placeholderText`.** O comentário diagnostica o defeito com precisão, nomeia o mecanismo — "a cor
do texto a 50 % de alfa" — e a regra que ele escreve não o toca.

**Como reproduzir:**
```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.contraste --saida <tmp>
   → "QPalette.Active: PlaceholderText sobre Base" razao=7.0769  portao=true

..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\c5\c5_contraste_dica.py
   → classica  Dataset carregado, habilitado=True  -> 3.96:1  ABAIXO DE 4,5:1
```

**Por que reprova, em três linhas da carta:**
- **§3.3** — *"Contraste abaixo de WCAG AA em qualquer par"* é um defeito que reprova sozinho, e
  este é medido no pixel, em componente ativo, no estado permanente de uma aba.
- **§6** — *"Se um portão numérico foi reportado pelo construtor, você mede de novo. (…) Se você não
  conseguir reproduzir a medição, o veredito é REPROVADO com a justificativa 'métrica não
  reproduzível'."* Reproduzi **212 dos 213 pares sob portão** ao decimal. Este eu não reproduzo:
  7,08 contra 3,96.
- **§5.3** — o par está *dentro* do `PASSOU` que o relatório publica. Um portão que aprova um par
  que a tela reprova é a mesma família do defeito nº 5 do ciclo 1, do nº 1 do ciclo 3 e do nº 3 do
  ciclo 3: **um instrumento afirmando algo que o artefato não contém.** Deixar passar a quinta vez
  ensina que a régua errada funciona.

**O conserto é pequeno e tem duas metades, e as duas são obrigatórias:** uma declaração de cor de
dica na folha (`QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox { placeholder-text-color: … }`
com um token que passe 4,5:1 sobre `Base` nas duas peles), **e** o arnês compondo o alfa antes de
calcular a razão — senão o portão continua incapaz de cobrar o conserto que acabou de receber.

---

## §7 — Defeitos não bloqueantes

1. **O estado vazio da aba principal manda apertar um botão que não existe.**
   `qt/painel_de_resultado.py:87-90`:
   *"Nenhum diagrama aberto. Clique num diagrama marcado da página, ou use **"Ler página"** para ler
   a página inteira."* Sondei os controles visíveis nas duas peles: **0 controles chamados "Ler
   página"**. O comando existe (`ler_pagina`) e aparece com **três nomes, nenhum deles esse**:
   `rotulo` = "Ler esta página" (menu e dica), `rotulo_curto` = "OCR todos diagramas" (pílula da
   pele Foco) e, na pele **clássica**, **`text=''`** — um botão **só de ícone** na barra do visor,
   sem rótulo nenhum. Está nas 6 capturas de Resultado. É pior que estado vazio sem orientação: é
   orientação que aponta para o lugar errado. *(Uma linha de string, ou `rotulo_curto` no lugar do
   literal.)*
2. **Sete ícones, cinco grades, tinta de 30,6 % a 65,7 %, e um deles é um caractere de 4×5 px.**
   Números no critério 7. Carta §3.3.
3. **As 36 capturas — e todas as medidas offscreen — são feitas em `Alef`, não na `Segoe UI` do
   produto.** `capture.py` sobe com `QT_QPA_PLATFORM=offscreen` + `QT_QPA_FONTDIR=C:\Windows\Fonts`;
   nesse ambiente `QApplication.font().family()` é `"Sans Serif"`, que o Qt resolve para **`Alef`**
   (uma família hebraica instalada nesta máquina). Na plataforma real ele resolve para **`Segoe
   UI`**. Métricas medidas por mim nos dois:

   | amostra | Alef (as capturas) | Segoe UI (o produto) | diferença |
   |---|---|---|---|
   | `Copiar headers para todos` (CORPO) | 143,00 px | 138,00 px | Alef **+3,6 %** |
   | a frase do estado vazio da aba Texto | 653,00 px | 625,00 px | Alef **+4,5 %** |
   | altura de linha de `TITULO` | 22,00 px | 21,00 px | +1 px |

   **A direção é conservadora** para "nada está cortado" e para "cabe em 1366×768" — o texto real é
   mais estreito que o medido —, e por isso não bloqueia. Mas o critério 6 é julgado sobre imagens
   numa fonte que o usuário nunca verá, e o eixo `ACAO` perde de metade a dois terços da força
   (critério 6). O `capture.py` já tem um docstring inteiro sobre "sem fontes a captura mede tofu";
   ele consertou o tofu e não conferiu a família.
4. **O detector de thread invisível pega 1 de 6 grafias e marca 1 de 6 como registrada sem
   registro.** §5.
5. **11 de 12 painéis a 1920 têm mais de 200 kpx a 0 % de tinta**, e a aba Estudo piorou 9,8 %.
   0 de 12 a 1366 e a 1280. Declarado pelo construtor; o número exato é meu (critério 4).
6. **A coluna "Motivo" da Revisão continua ilegível**: contei nas capturas os itens cujo texto chega
   à borda da coluna — **18 de 27 a 1920** (eram 17 no c2), **25 de 27 a 1366 e a 1280**. É o texto
   que diz por que o item está na fila.
7. **A aba Estudo tem 29 botões em 4 filas a 1920 e 5 filas a 1366 e a 1280**, contra o alvo de
   ≤ 12 em ≤ 2. `.md` / `.html` / `.rtf` continuam três botões permanentes.
8. **A tabela do Dataset precisa de barra horizontal a 1280 e a 1366**, e agora precisa mais,
   porque o conserto do cabeçalho ("Conjunt" → "Conjunto") alargou as colunas honestamente. Declarado.
9. **A janela recusa 1024×768**: `1066×735` (claro) e `1066×769` (escuro), **42 px de largura acima
   do alvo de ≤ 1024×700**. Declarado, com a causa isolada.
10. **O `contraste.json` e o `teclado.json` sobrescrevem** (nome fixo, sem carimbo de data), e
    `casos_ruins.py`, `titulo_longo.py` e `estados.py` cravam pasta **e prefixo `c1_`**. Foi o que
    matou 14 capturas no ciclo 4, 3 no ciclo 3 e por pouco não matou o `contraste.json` na minha
    sessão (§Nota). Três linhas de `argparse`.
11. **A dica dentro do campo desabilitado fica em 2,21:1 (claro) e 2,88:1 (escuro).** WCAG isenta
    componente inativo, e por isso isto **não** é o bloqueante — mas é o mesmo alfa, e o conserto do
    bloqueante o resolve de graça.
12. **Duas das quatro pílulas da pele Foco duplicam botões visíveis na mesma tela**, e o tabuleiro
    da pele escura é **9,2 % menor em área** a 1920. Intocado desde o ciclo 1.
13. **`Modo bloco (lento)`** e os **dois controles sem rótulo visível na aba Texto** (o spinner `1`
    e o combo `auto`) continuam como estavam.
14. **A caixa de legenda da Galeria é um retângulo de 782×170 px cujo interior mede
    770×158 = 121,7 kpx a 0,00 % de tinta**, sem rótulo e sem `placeholderText`, entre a fila de
    navegação e `Copiar legenda`. É o único poço grande da janela que não diz o que espera receber.
15. **A aba Dataset diz "Lendo o dataset" duas vezes ao mesmo tempo** — no centro do painel e na
    zona de mensagem do rodapé, a ~500 px de distância. É a mesma redundância que o §7.10 do ciclo 3
    mandou apagar na Galeria, num painel diferente.

---

## §8 — O que funciona, e o que este ciclo conquistou

A carta §5.5 manda nomear. Nomeio:

1. **Os três bloqueantes do ciclo 3 estão fechados**, e verifiquei os três com os instrumentos do
   próprio crítico que os levantou: 0 leituras de `csv` e 0 chamadas de `labels._clean` na
   `MainThread` por virada; 8 indicadores e 13 threads todas visíveis; ΔRGB de `hover` entre 15 e 36
   nas 8 pranchas, recalculado por mim a partir dos PNGs, com **0 divergências** contra o manifesto.
2. **A virada de página caiu de 171,4 ms para 98,8–101,2 ms**, e a parte desta frente de **34 %
   para 1,5–2,3 %**. É o item mais difícil dos três e o mais bem fechado.
3. **A janela de 400 ms fechou de verdade, e não por sorte de relógio.** Com os relógios do rodapé
   afastados para 10 s, um registro vindo de **thread de trabalho** acende a barra em **2,9 ms**.
4. **As 36 capturas não se contradizem, e o placar é 8 ociosas / 28 ocupadas, sem exceção.**
   O construtor disse "0 contradizem-se"; o censo de pixel confirma e é bimodal sem sobreposição.
5. **O visor finalmente cresce com a janela**: 366 px nas três larguras → **520 / 557 / 800 px**,
   97,7 % do viewport a 1920. Era *"abrir num monitor maior dá mais branco"*.
6. **O vão entre tabuleiro e paleta fechou de 203 px para 16 px**, e a largura vazia da faixa do
   tabuleiro caiu de 39,2 % para 32,8 % do painel.
7. **A escala de tipos passou o alvo com folga e o eixo novo é real no pixel**: 64,5 % na pior das
   18 combinações (era 92,5 %), e `TITULO` acrescenta +195 % a +214 % de tinta na fonte do produto.
8. **O divisor não apaga mais nada.** `childrenCollapsible=False`, alça de 6 px, e o arrasto até os
   extremos trava em `[540, 820]` e `[840, 520]` — **0 de 36 controles fora da janela em qualquer
   posição**, faixa de abas sempre visível. Era 21 de 36.
9. **Zero texto espremido e zero cabeçalho cortado**, em **36 combinações** de aba × pele × tamanho,
   medidos pela régua do próprio Qt (`width() < sizeHint().width()`). O `onf. min` acabou, o
   `Conjunt` acabou, e o conserto é dinâmico — refeito a cada `FontChange`/`StyleChange`.
   *(Registro que o `colapso.py` do ciclo 3 acusa "NAO CABE" em rótulos que cabem: ele subtrai 16 px
   fixos de todo widget, e um `QLabel` dimensionado ao conteúdo tem `width() == advance`. É falso
   positivo do instrumento, não defeito do produto.)*
10. **`Gravar` alinhado ao pixel**, cinco botões em x=825 largura 218, desalinho **0 px**.
11. **5 de 5 comandos rebaixados com tecla global**, 25 ações com tecla contra 21.
12. **A fronteira `ui/` × `qt/` continua intacta**: 58 módulos, **0** imports de toolkit ou de `qt/`
    por varredura AST minha, 110 testes verdes em 0,62 s num venv sem binding.
13. **A suíte do tronco é estável em duas execuções completas**, linha final idêntica campo a campo,
    e o caminho que causava o `access violation` não derruba mais o processo.
14. **O construtor achou três defeitos olhando, consertou os três, achou um quarto que era dele
    próprio, e publicou os quatro.** Mais a divulgação das 14 capturas. Esse comportamento é o
    motivo pelo qual esta frente está a uma linha de folha de estilo da aprovação, e ele deve
    continuar.

---

## §9 — O que precisa mudar para eu aprovar

### Bloqueante — um só

1. **Dê cor própria ao texto de dica do campo, e ensine o arnês a compor o alfa.** Duas metades,
   as duas obrigatórias:
   - `ui/folha_de_estilo.py`, bloco `campos`: declare `placeholder-text-color` (ou o papel
     equivalente) para os dez seletores, com um token que dê **≥ 4,5:1 sobre `Base` nas duas
     peles**. Hoje o Qt deriva a dica da cor de texto a **alpha 128**, e a linha
     `QLineEdit[echoMode="0"] { selection-background-color: … }` (linha 499), cujo comentário
     promete consertar isto, não a toca. **Corrija o comentário junto com o código.**
   - `caissa/ui/audit/contraste.pares_da_paleta`: componha o alfa sobre o fundo **antes** de calcular
     a razão, ou leia a cor da `QPalette` viva em vez do token. Enquanto o par for resolvido pelo
     token opaco, o portão publica 7,08:1 para uma tela de 3,96:1 e não consegue cobrar o conserto.
   *Alvo, cobrado por teste: `PlaceholderText` composto sobre `Base` **≥ 4,5:1** nas duas peles no
   relatório do arnês, **e** `≥ 4,5:1` medido no `grab()` de um `QLineEdit` habilitado com dica —
   porque este é o quinto instrumento desta frente a afirmar o que a tela não contém, e o número tem
   de vir do pixel.*

### De desenho — não bloqueiam

2. **Troque `"Ler página"` pelo nome que o botão realmente tem.** `painel_de_resultado.MENSAGEM_VAZIA`
   nomeia um controle que não existe em nenhuma das duas peles; o comando aparece como "Ler esta
   página" (dica), "OCR todos diagramas" (pílula) e **sem rótulo nenhum** (ícone, pele clássica).
   Use `comandos.CATALOGO["ler_pagina"].rotulo_curto` em vez do literal — e dê rótulo ou dica visível
   ao botão na pele clássica. *Alvo: 0 estados vazios citando texto que não aparece em nenhum
   controle visível, cobrado por um teste que cruza as mensagens com os rótulos do catálogo.*
3. **Alargue o detector de thread do portão e do `test_busy`.** Hoje `FORMAS_DE_THREAD` tem duas
   grafias literais e `_registra` aceita qualquer nome contendo `registrar`. Plantei seis operações
   de fundo não registradas: **detectou 1, marcou 1 como REGISTRADA, não viu 4**. Reconheça pelo
   menos `Thread` importado direto, subclasse de `threading.Thread`, `threading.Timer` e
   `concurrent.futures`; e exija que o `register` encontrado seja do `BusyRegistry` e não qualquer
   nome com `registrar`. *Alvo: `benchmarks\reports\critique\ui\c5\sabotado\` acusar **6 de 6**.*
4. **Uma grade de ícones só.** Sete botões só-de-ícone na barra do visor, cinco caixas de glifo
   (14×10, 14×8, 12×14, 12×12, 11×11, 4×5) e tinta de 30,6 % a 65,7 %. O `×` é um caractere de texto
   de 4×5 px num botão de 26 px. *Alvo: caixa de glifo única (±1 px) e tinta/caixa dentro de uma
   faixa de ±20 % relativo, nos sete.*
5. **Capture na fonte do produto.** `capture.py` mede em `Alef` porque `"Sans Serif"` é o que o
   offscreen entrega; a plataforma real dá `Segoe UI`, que é **3,6 % a 4,5 % mais estreita**. Force a
   família (`QApplication.setFont(QFont("Segoe UI", 9))`) ou registre no nome do arquivo em que
   fonte a captura foi feita. *Alvo: `QFontInfo(...).family()` das capturas igual ao da plataforma
   real, afirmado pelo próprio `capture.py`.*
6. **Ataque o vazio de tela grande, que é o único critério dos nove que não passa.** 11 de 12
   painéis acima de 200 kpx a 1920 e **0 de 12** a 1366 e a 1280 — é um defeito de monitor grande, e
   os três maiores são a Revisão (391,0 kpx de corpo de tabela não usado), o Texto (421,8 kpx acima
   do estado vazio) e o Dataset (371,7 kpx). *Alvo do §2.4 mantido: nenhuma região acima de 200 kpx
   com menos de 2 % de tinta, medido por `c5_vazios.py`, que devolve o máximo exato.*
7. **Publique a ocupação contra o painel, não contra a caixa da paleta.** 86,2 % é a ocupação numa
   caixa que termina onde a emptiness nova começa; contra o painel são **59,4 %**. O vão fechou de
   verdade (203 px → 16 px) e isso merece ser dito com a régua que não muda entre os ciclos.
8. **Encolha a tabela da Revisão ou traga a fila de ações para junto do dado** (391,0 kpx a 1920),
   e **dê largura ao "Motivo"**: 18 de 27 linhas ilegíveis a 1920, 25 de 27 a 1366.
9. **Ponha `--saida` nos cinco instrumentos que gravam com caminho cravado** (`casos_ruins.py`,
   `titulo_longo.py`, `estados.py`) **e carimbe a data em `contraste.json` e `teclado.json`.**
   Este defeito já custou 17 capturas em dois ciclos.
10. **Dê rótulo ou `placeholderText` à caixa de legenda da Galeria** (782×170 px de poço mudo) e
    **apague a segunda "Lendo o dataset"** — a do centro do painel ou a do rodapé, uma das duas.
11. **A aba Estudo continua com 29 botões em 4–5 filas** contra o alvo de ≤ 12 em ≤ 2, e a pele
    Foco continua duplicando dois botões nas pílulas e custando 9,2 % da área do tabuleiro.

---

## §10 — Como reproduzir

```bat
:: portões
.venv\Scripts\python.exe -m pytest tests\unit\ui\ -q
.venv\Scripts\python.exe -m caissa.ui.audit.contraste --saida benchmarks\reports\critique\ui\c5
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --saida benchmarks\reports\critique\ui\c5
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONPATH=<suite>\src;<tronco>\src
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado  --pdf "…\1937 Kemeri.pdf" --saida …\c5
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio --pdf "…\1937 Kemeri.pdf" --saida …\c5   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.quadros  --pdf "…\1937 Kemeri.pdf" --saida …\c5   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly   :: no tronco, 2x

:: instrumentos do ciclo 3 (nenhum grava arquivo -- conferi antes de rodar)
c3\quem_chama.py  <pdf>     :: 0 leituras completas do labels.csv por virada
c3\qual_thread.py <pdf>     :: 0 chamadas de labels._clean na MainThread
c3\detalhes.py    <pdf>     :: Gravar em x=825, uma frase na Galeria, barra invisivel
c3\colapso.py     <pdf>     :: 0 de 36 fora da janela; a secao "NAO CABE" tem falso positivo de 16 px
c3\medidas_c3.py  pagina <png…>   :: 520 / 557 / 800 px
sobreposicao.py             :: 1066x735, 0 fora, 1 sobreposicao isenta

:: instrumentos deste ciclo (benchmarks\reports\critique\ui\c5\)
c5_tipos.py       :: censo PEDIDO x RESOLVIDO por aba/pele/tamanho -> 64,5 % no pior caso
c5_fonte.py {offscreen|real}  :: Alef x Segoe UI, e as metricas dos dois
c5_peso.py  {offscreen|real}  :: o peso 600 no pixel: +37 % em Alef, +5,4 a +13,6 % em Segoe UI
c5_casos.py       :: 0 espremidos, 0 cabecalhos cortados, spinner 289, "Ler pagina" = 0 controles
c5_regioes.py <png…>   :: vao tabuleiro-paleta 16 px, ocupacao 59,4 % contra o painel
c5_vazios.py  <png…>   :: o MAIOR retangulo vazio exato de cada painel
c5_janela400.py   :: a barra acende em 2,9 ms com o relogio em 10 s; release pos-morte nao derruba
sabotado\         :: copia do tronco com 6 operacoes de fundo plantadas (o tronco NAO foi tocado)
   .venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco …\c5\sabotado --saida …\c5
```

Artefatos meus em `benchmarks\reports\critique\ui\c5\`: os sete instrumentos, a cópia sabotada,
`tronco_run1.txt`, `tronco_run2.txt`, `bloqueio_fps_c5.txt`, `custo_aviso_c5.txt`, `teclado.json`,
os recortes ampliados `z_icones_visor_claro.png`, `z_icones_zoom_claro.png`,
`z_pilulas_escuro.png`, `z_esc1366_topo.png`, `z_cla1366_topo.png` e as amostras de tipo `t_*.png`.
**Nada fora desta pasta e deste documento foi escrito por mim**, com a exceção declarada do
`contraste.json` (mesmo conteúdo, campo `quando` novo).

---

## §11 — Veredito

**REPROVADO — por um defeito, e ele não é de desenho.**

Os **três bloqueantes do ciclo 3 estão fechados**, e não estou aceitando a palavra do construtor:
rodei os instrumentos do próprio crítico que os escreveu. A virada de página faz **zero** leituras
do `labels.csv` e **zero** chamadas de `labels._clean` na thread da janela, e caiu de 171,4 ms para
**98,8–101,2 ms**, com a parte desta frente em **2 %**. O portão de progresso lista **8** operações
e **13** threads, nenhuma invisível, e a barra do rodapé **some quando não há o que mostrar** —
verificado nas 36 capturas, 8 ociosas e 28 ocupadas, **sem uma única contradição**. A janela de
400 ms fechou por **sinal** e não por relógio: **2,9 ms** com os relógios afastados para 10 s. O
`hover` finalmente existe na prova, com ΔRGB de 15 a 36 e 91 %–99,7 % dos pixels mudando, **0
divergências** contra o manifesto. E a suíte do tronco é **estável em duas execuções completas**,
sem o `access violation` — inclusive no caminho exato que o causava.

Também não encontrei afrouxamento, e procurei: 216 focáveis com nome e papel, 287/213/0 no
contraste, 110 testes de fronteira num venv sem Qt, 58 módulos de `ui/` com **0** imports de
toolkit, 36 capturas com a dimensão que o nome anuncia, **0** rótulos espremidos e **0** cabeçalhos
cortados em 36 combinações de aba × pele × tamanho. E a divulgação das 14 capturas destruídas foi
tratada **corretamente** — mais corretamente que a do ciclo 3, que perdeu três e não disse nada.

Não aprovo por **um** motivo, e ele é o motivo que esta frente já ouviu quatro vezes com outros
nomes: **um instrumento afirma o que a tela não contém.** O texto de dica do campo de busca do
Dataset, com o campo **habilitado** e a leitura concluída — o estado permanente da aba — fica em
**3,96:1** na pele clara, abaixo do piso de 4,5:1 da WCAG AA. O portão de contraste publica
**7,08:1** para exatamente esse par, com `portao: true` e sem nota de isenção, porque resolve a cor
pelo **token opaco** e nunca compõe o **alpha 128** com que o Qt desenha a dica. Reproduzi 212 dos
213 pares sob portão ao decimal; este não reproduz, e a carta §6 chama isso pelo nome. E o
comentário imediatamente acima da linha responsável descreve este defeito com precisão — *"a cor do
texto a 50 % de alfa (…) cai abaixo do piso AA sem que nenhuma tabela de cor saiba"* — e a regra que
ele escreve ajusta o **realce da seleção**.

É meia linha de folha de estilo e uma linha de arnês. Feito isso, e feito o item 2 do §9 (o estado
vazio da aba principal que manda apertar um botão inexistente, que é uma string), **aprovo**: os
itens 3 a 11 são de desenho e de instrumento, e nenhum deles impede um enxadrista profissional de
trabalhar nesta janela.
