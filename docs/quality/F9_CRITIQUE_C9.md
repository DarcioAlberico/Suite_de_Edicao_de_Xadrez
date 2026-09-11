# F9 — Interface, crítica do ciclo 9

```
VEREDITO: REPROVADO
CICLO: 9
FRENTE: F9 (Interface)
```

**Reprova por uma coisa só, e ela não estava no placard de nenhum dos dois lados.**

Os dez itens que o ciclo 8 declarou eu remedi — **os dez**, não os sete pedidos — e os dez batem.
A autodenúncia do arnês é verdadeira: capturei as 36 duas vezes, partindo de estados de sessão
opostos, e as 36 saem **idênticas em tudo que o relatório mede**. O número do §6 é o honesto.

O que reprova é o **nono instrumento cego, e ele é cego por escopo e não por regra**: o portão de
teclado/nome/papel — que o relatório publica como *"216 focáveis, 0 sem nome, 0 sem papel,
PASSOU"* — roda numa das **três** peles que o produto oferece em `Ver ▸ Aparência`. Rodei o mesmo
portão, sem alterar uma linha, nas outras duas:

```
  CVOFF_SKIN=classica   216 focaveis   0 sem sentido   PASSOU
  CVOFF_SKIN=foco       240 focaveis   2 sem sentido   REPROVOU
  CVOFF_SKIN=fita       360 focaveis  36 sem sentido   REPROVOU
```

E os 36 da pele `fita` são, palavra por palavra, o defeito nº 1 do **ciclo 1** desta frente —
controles que chegam ao leitor de tela como `-`, `+`, `◀`, `▶`, `|◀`, `▶|` — mais um defeito
visual que o ciclo 8 acabou de criar ali: **os mesmos seis botões desenham o ícone novo *e* o
glifo velho, lado a lado**. O `◀` de 5×3 px que o ciclo 7 mediu e o ciclo 8 apagou está na tela,
encostado no desenho que era para substituí‑lo.

---

## Nota de procedimento

Rodei todos os portões do zero, com `--saida` sempre para
`benchmarks\reports\critique\ui\c9\`. **Conferi o destino e a entrada de cada script antes de
rodá‑lo** — e valeu a pena duas vezes:

* `benchmarks\reports\critique\ui\c7\c7_zoom.py` grava na pasta **do ciclo 7**. Não o rodei;
  copiei‑o para `c9_zoom.py` com o destino trocado.
* `benchmarks\reports\critique\ui\c7\c7_cor_e_bordas.py` tem a **entrada** cravada
  (`Image.open(C6 / nome)`): rodado com as minhas capturas como argumento, ele lê as do ciclo 6
  e imprime os números de lá. Não destrói nada, mas mente sobre o que mediu. Refiz o censo de
  matiz com código meu, sobre as minhas capturas.
* `benchmarks\reports\ui\c6\c6_aberto.py` escreve `capture_estado.json` — conferi: em
  `tempfile.mkdtemp()`, fora do repositório. Rodei.

Para medir o determinismo eu precisei **envenenar** `data/app_tkinter_state.json` do tronco (é o
arquivo que o defeito autodenunciado usa). Copiei‑o antes para
`c9/BACKUP_app_tkinter_state.json`, envenenei duas vezes e restaurei: conferido campo a campo, o
arquivo está idêntico ao que estava. Fora disso, **nada foi escrito fora de
`docs\quality\F9_CRITIQUE_C9.md` e de `benchmarks\reports\critique\ui\c9\`.**

Instrumentos novos meus, todos em `benchmarks\reports\critique\ui\c9\`, nenhum grava fora dela:

| instrumento | o que responde |
|---|---|
| `c9_determinismo.sh` | captura as 36 a partir de um `sash_fraction` envenenado |
| `sab_c9/` | **oito formas novas** de operação de fundo, + 4 controles negativos |
| `sab_c9_prog/` | oito formas contra a heurística nova de "total conhecido" |
| `c9_faixa_tardia.py` | `determinado` sobrevive a uma faixa que muda depois de lida? |
| `c9_cromo_menu.py` | `nomear_o_que_o_cromo_nao_desenha` contra menu, botão escondido e rótulo |
| `c9_vazio_no_piso.py` | o estado vazio nas **3 peles** e no piso da janela (1066), e **quantas vezes** o nome é desenhado |
| `c9_fen_estados.py` | a marca da FEN com o cursor no **fim** e com a fonte maior sem `resize` |
| `c9_icones_com_texto.py` | o censo de ícones **incluindo** os botões com texto |
| `c9_tipografia_na_tela.py` | 864 strings desenhadas × 5 regras tipográficas |
| `c9_estado_morto.py` | o botão desabilitado **lê‑se** como desabilitado? |
| `c9_orfas.py` | viúvas e órfãs nas frases de estado vazio |
| `c9_quatro_k.py` / `c9_pele_fita.py` | os dois pedaços do §3.2 que ninguém fotografou |

**Duas vezes o meu olho errou e a régua acertou**, e registro as duas: (a) achei que o ícone e o
texto de `OCR todos diagramas` se encostavam — a lacuna é de **4 px**, a mesma do paginador, e
não afirmo defeito; (b) achei que a marca da FEN comia o último caractere digitado — não come,
o índice 72 continua alcançável dentro da margem nas 16 medições do estado B.

---

## §1 — Comparação às cegas (substituição do §2.1)

Mantida a substituição das rodadas anteriores: os **nove critérios de desenho**, cada um com a
pergunta *"isto sobrevive ao lado do Affinity Publisher, do Chessbase 17 e do Scrivener?"*, e a
medida que sustenta a resposta. Tudo abaixo saiu das **minhas** capturas (`c9/capA/`), não das
publicadas.

### 1. Hierarquia visual — **SOBREVIVE NA PELE PADRÃO; NÃO SOBREVIVE NA `fita`**

O bloqueante do ciclo 7 está morto e eu tentei matá‑lo em mais estados do que o construtor
amostrou. `c9_vazio_no_piso.py`, **3 peles × 4 larguras**, incluindo o piso de 1066 que nenhum
instrumento tocou:

```
  0 nomes citados NAO desenhados   (36 linhas: 3 peles x 4 larguras x 3 nomes)
  'OCR todos diagramas'  desenhado por EXATAMENTE 1 controle visivel em todas as 12 combinacoes
  'Achar no texto…'      1
  'Ler folha'            2  -- a barra + o botao dentro do vazio (padrao declarado no ciclo 2)
```

Fechar o item **sem** abrir o item 11 é a metade difícil, e ela fechou: nunca dois, nunca zero,
nem a 1920 nem a 1066, nem na `fita`.

O que **não** sobrevive é a `fita`: 20 botões em duas filas de ~48 px, **sem cabeçalho de grupo
visível**, seis deles desenhando ícone + glifo. Ver `zfita_1366x768_resultado.png`. O Affinity não
imprime uma fita em que quatro botões de navegação carregam um triângulo desenhado e um traço de
5×3 px ao lado dele.

### 2. Ritmo espacial — **NÃO SOBREVIVE**

`c6_aberto.py` do construtor, sem alteração, rodado por mim:

```
  1920: Estudo 29 botoes em 4 filas [(12,8), (42,10), (72,4), (108,7)]
  1366: Estudo 29 botoes em 6 filas [(12,6), (42,2), (72,9), (108,1), (138,4), (168,7)]
  1280: idem                                              ^^^^^^^^ uma fila com UM controle
```

O alvo do ciclo 3 (≤ 12 botões em ≤ 2 filas) continua reprovando por 2,4×, e a fila de um
controle só continua lá — visível a olho nu em `capA/c9_escuro_1366x768_estudo.png`.

O tabuleiro da Estudo é **577×577** a 1920: 577/8 = **72,125 px** por casa. As casas continuam
sem fechar num inteiro (era 585/8 = 73,125 no ciclo 7). Um editor AAA escolhe 576 ou 584.

### 3. Alinhamento — **SOBREVIVE, com uma medida contra**

**Os onze glifos de texto morreram na pele padrão, e eu confirmo com o instrumento do ciclo 7 sem
tocá‑lo**: `GLIFOS DE TEXTO fazendo papel de icone: 0` (eram 11). Caixa única **16×16**,
amplitude **0 px de largura, 0 px de altura**. Isso é conquista real.

Mas a régua com que o número é publicado (`c8_icones_da_janela.py`) filtra assim:

```python
if tem_icone and not texto:
```

**Todo botão que tem ícone *e* texto fica fora da medição** — e foram exatamente esses que este
ciclo criou. São três, e um deles é o botão que fecha o bloqueante:

```
  Resultado  'OCR todos diagramas'  16px  caixa 16x16  tinta  94 px2  36.7 %
  Galeria    'anterior'             16px  caixa 16x16  tinta  46 px2  18.0 %
  Galeria    'próximo'              16px  caixa 16x16  tinta  45 px2  17.6 %
```

Incluí‑los **não piora** o número publicado (a caixa continua única, a tinta continua 17,6–41,4 %),
e digo isso porque é o que a medição mostra. O que a medição mostra também é que, **dentro de um
mesmo grupo de irmãos**, que é onde o olho compara:

```
  Galeria / paginador de 4 botoes:  |◁  ◁anterior  ▷proximo  ▷|
      Primeiro diagrama   tinta 87 px2  34.0 %   triangulo FECHADO + barra
      Diagrama anterior   tinta 46 px2  18.0 %   chevron ABERTO
      Proximo diagrama    tinta 45 px2  17.6 %   chevron ABERTO
      Ultimo diagrama     tinta 83 px2  32.4 %   triangulo FECHADO + barra
      -> 1,9x de massa e DUAS linguagens de seta na mesma fila
```

A regra que o ciclo 8 declarou é *"as de item são abertas (V), as de página são triângulos
cheios"*. Os quatro botões acima são **todos de item** (primeiro/anterior/próximo/último
*diagrama*), e dois deles usam a linguagem de página. É o defeito `◀`/`▶` do ciclo 7 com a
amplitude caindo de 2,4× para 1,9× e mudando de causa. Não bloqueia; entra no §6.

### 4. Densidade × vazio — **NÃO SOBREVIVE a 1920, e piora com a tela**

`c5_vazios.py` e `c5_regioes.py` do crítico do ciclo 5, sem uma linha alterada, sobre as
**minhas** 36:

| painel (1920) | claro | escuro |
|---|---|---|
| Texto | **425,0 kpx** (1052×404) | 408,2 |
| Revisão | **394,0** (1048×376) | 360,5 |
| Dataset | **370,3** (1052×352) | 353,5 |
| Estudo | 281,5 | 268,0 |
| Galeria | 224,0 | 208,0 |
| Resultado | 118,7 | 135,6 |

**10 de 12 acima de 200 kpx a 1920; 0 de 24 a 1366 e a 1280.** Idêntico à decimal ao que o
construtor publicou — e ele publicou a partir de capturas que eu reproduzi de um estado
envenenado. Item 6 aberto e declarado sem atenuar; a declaração está certa.

Item 7, com a régua do crítico: **ocupação 73,1 % claro / 69,7 % escuro**, vão tabuleiro→paleta
**16 px**, **114,5 kpx a 0,00 % de tinta** à direita da paleta. Os três números do §6 batem.

**O que ninguém mediu é o outro lado do §3.2 da carta — "e para 4K".** Oito ciclos mediram 1024,
1280, 1366 e 1920. Abri a 2560×1440 e a 3840×2160 (`c9_quatro_k.py`):

| | 1920 | 2560 | 3840 |
|---|---|---|---|
| Resultado, ocupação do canvas | 73,1 % | **87,9 %** | **89,4 %** |
| Resultado, maior vazio | 118,7 kpx | 16,4 | 43,3 |
| **Estudo, maior vazio** | 281,5 kpx | **593,9** | **1 569,6** |

O Resultado **melhora** quando a tela cresce, e isso é desenho bom. O Estudo piora: a 4K são
**1,57 megapixels** de nada num painel de 2126×2071, porque o tabuleiro para de crescer e a
coluna de lances não ocupa a sobra. É o painel que já reprovava a 1920, e ele reprova mais no
monitor de quem edita material para publicação.

### 5. Cor como sinal — **SOBREVIVE. Continua o melhor item da frente.**

Censo de matiz meu, restrito ao cromo (painel esquerdo, sem o visor), saturação > 0,25, sobre as
minhas capturas:

| captura | % do cromo em cor | famílias |
|---|---|---|
| `c9_claro_1920x1080_texto` | **0,04 %** | **210° apenas** |
| `c9_escuro_1920x1080_texto` | 0,04 % | **210° apenas** |
| `c9_claro_1920x1080_galeria` | 0,06 % | **210° apenas** |
| `c9_escuro_1920x1080_galeria` | 0,06 % | **210° apenas** |
| `c9_claro_1920x1080_revisao` | 0,08 % | **210° apenas** |
| `c9_escuro_1920x1080_revisao` | 0,08 % | 210° (+225° residual) |

Um matiz, menos de um décimo de por cento da superfície, idêntico entre as peles e estável há
três ciclos. Nível Affinity.

### 6. Tipografia da interface — **SOBREVIVE, e agora com um número que ninguém tinha**

As aspas retas fecharam, e eu não confiei nas três frases. Varri **tudo que a janela desenha** —
`text()` de botão, rótulo, aba, cabeçalho de grupo, `placeholderText`, e o texto dos itens de
menu — nas três peles (`c9_tipografia_na_tela.py`):

```
  864 strings desenhadas lidas em 3 peles

  aspa reta ("):                       0
  apostrofo reto ('):                  0
  "..." em vez de "…":                 0
  hifen entre espacos (travessao?):    0
  faixa numerica com hifen:            0
```

**Zero em 864.** Isso é mais do que o construtor afirmou (ele afirmou 3 de 3 frases) e é a régua
certa: a carta §3.3 fala do produto, não de três strings.

**Uma ressalva medida, e ela é do mesmo bloco da carta — "viúvas e órfãs não tratadas".** Nenhum
ciclo olhou a última linha de nenhum parágrafo. `c9_orfas.py`, 3 peles × 3 larguras, sobre os
`QLabel` com quebra:

```
  54 paragrafos com quebra medidos; 8 com ultima linha ORFA
  classica 1280  medida 627 px  ultima linha 'inteira.'                36 px =  5.7 %  <<< ORFA
  classica 1366  medida 389 px  ultima linha 'onde parou.'             57 px = 14.7 %  <<< ORFA
  classica 1920  medida 671 px  ultima linha 'e continua de onde parou.' 126 px = 18.8 % <<< ORFA
```

A pior é `'inteira.'` — **uma palavra, 5,7 % de uma medida de 627 px, centrada** — e ela é a
última linha da `MENSAGEM_VAZIA`, a primeira frase que o produto mostra. É a frase que este ciclo
reescreveu. Recorte em `z_gal_orfa.png`.

### 7. Controles — **NÃO SOBREVIVE, e a causa não é a que os dois lados achavam**

Repouso × pressionado × desabilitado foi medido no ciclo 7 como *"97,6 % dos pixels mudam no
pressionado e 98,9 % no desabilitado"*. **"Quantos pixels mudam" não é "o estado se lê".**
Medi a distância que o olho usa — a tinta do rótulo contra a face do próprio botão
(`c9_estado_morto.py`):

```
  pele classica: 54 rotulos vivos, 23 mortos
     vivo  8.79..20.31:1 (mediana 20.31)   morto 6.54:1
     rotulos MORTOS com contraste >= o rotulo VIVO mais fraco:  0 de 23
  pele foco:     58 rotulos vivos, 22 mortos
     vivo  5.71..11.02:1 (mediana 11.02)   morto 7.14:1
     rotulos MORTOS com contraste >= o rotulo VIVO mais fraco: 22 de 22   <<<
```

E as duas distâncias, em razão de contraste entre o estado vivo e o morto:

```
  FACE  do botao:   1.10:1 (classica)   1.22:1 (foco)
  TINTA do rotulo:  2.82:1 (classica)   1.88:1 (foco)
```

Na pele Foco o estado morto é sinalizado por **1,88:1 de tinta e 1,22:1 de face**. O portão de
contraste do próprio produto usa **3,0:1** como piso para "informação que não é texto" — uma
listra de tabela, uma marca. O produto aplica 3,0:1 a uma listra e **1,88:1** a *"você não pode
apertar isto"*. É por isso que, ampliando `z_foco_painel.png` a 2×, eu não consegui dizer qual
`Salvar a posição` estava cinzento — e é a causa mecânica do item 8, que os dois lados
descreveram sem achar.

O resto do critério está bem: o anel de foco existe e é visível (168 px azuis contra 0 no vizinho,
medido no ciclo 7 e confirmado na captura), e **os 2 pares com estados divergentes não são
armadilha**: cliquei na pílula viva `Salvar a posição` sem diagrama aberto e o rodapé respondeu
`"Não há diagrama lido para salvar: leia uma página antes."` — que é exatamente o que a carta
§3.3 pede de uma mensagem.

### 8. Estados vazios — **SOBREVIVE**

Três de três nomes citados desenhados por controle visível, em três peles, em quatro larguras,
**exatamente uma vez cada** (menos `Ler folha`, que é o padrão declarado). E o desenho que
resolve isso não consulta tabela: `nomear_o_que_o_cromo_nao_desenha` lê o `text()` do contêiner
do cromo. Julguei o desenho e testei‑o (`c9_cromo_menu.py`, seis cromos):

```
  1 cromo vazio (classica)          -> a barra NOMEIA          ok
  2 botao visivel com o nome        -> a barra NAO nomeia      ok
  3 nome quebrado em 2 linhas       -> a barra NAO nomeia      ok
  4 nome so dentro de um MENU       -> a barra NOMEIA          ok   <- a pergunta da ordem de servico
  5 botao ESCONDIDO com o nome      -> a barra NAO nomeia      <<< ERRADO
  6 QLabel com o nome               -> a barra NOMEIA          (duplicaria, mas duplicar e' o lado seguro)
```

**O caso do menu está certo**, e o argumento do construtor contra a tabela declarada está certo:
uma tabela "quem cada pele mostra" derivaria no dia em que alguém tirasse um comando do destaque,
que é a forma exata do defeito consertado. O caso 5 é o furo: o método lê `text()` **sem perguntar
`isVisible()`**, enquanto o portão que o cobra pergunta. Hoje nenhum dos três cromos monta botão
escondido (conferi `fila.py`, `fita.py` e `barra.py`: nenhum chama `hide()`/`setVisible(False)`),
então o número é verdade; falta **uma condição** para continuar sendo.

E a prova de vida do construtor usa exatamente esse furo — o cromo mentiroso é um `QWidget()` não
mostrado. A sabotagem funciona, mas ela prova a régua *através* do defeito do método.

### 9. A pele escura — **SOBREVIVE, e a `fita` NÃO ESTÁ NA CONVERSA**

Contraste: **296 pares / 218 sob portão / 0 reprovados** nas duas peles, menor folga **3,27:1** e
**3,03:1**. Listras próprias, superfície elevada própria, `pressionado` que escurece. Projetada,
não invertida.

Mas as **36 capturas são de duas peles**: `capture.PELES = (("classica","claro"),("foco","escuro"))`.
`ui/pele.PELES` registra **três**, e `Ver ▸ Aparência` oferece as três (`['Clássica','Foco','Fita']`,
lido do menu vivo). A `fita` é a única que muda a **densidade** (`COMPACTA`) — o eixo do item
*"espaçamento inconsistente entre elementos equivalentes"* da carta — e **nenhum instrumento
visual desta frente jamais a fotografou**: os censos de ícone cravam `CVOFF_SKIN="classica"`, os de
vazio e ocupação leem as 36, o de contraste percorre temas e não peles. Fotografei‑a
(`c9_pele_fita.py`, 18 capturas) e o §3 é o que apareceu.

---

## §2 — Os portões, remedidos (carta §6)

Três execuções onde a carta pede três; mediana reportada.

| portão | placard do construtor | minha medição | veredito |
|---|---|---|---|
| **Determinismo do arnês** | "consertado em `capture.py`" | **2 capturas de 36 a partir de `sash_fraction` 0,20 e 0,90** (+ página, zoom, geometria, aba e divisor da Estudo envenenados): 12/36 idênticas byte a byte, **24/36 diferem só numa caixa de 118×24 px do rodapé — a fase da marquise**. Linha central idêntica, divisor **x=1073** nas duas. Contra o conjunto **publicado**: 17/36 idênticas, as outras 19 só na mesma caixa | **CONFIRMADO** |
| Ocupação (item 7) | 73,1 % / 69,7 % / 16 px / 114,5 kpx | **idêntico à decimal**, na minha captura | **CONFIRMADO** |
| Vazio de painel (item 6) | 10 de 12 > 200 kpx; Texto 425,0 / Revisão 394,0 / Dataset 370,3 | **idêntico à decimal**; 0 de 24 a 1366 e 1280 | **CONFIRMADO** |
| Estado vazio na tela (item 1) | 30 de 30 `DESENHADO=sim` | **30 de 30** com o instrumento dele; e **36 de 36** com o meu (3 peles × 4 larguras), **0 duplicados** | **CONFIRMADO E ALARGADO** |
| Rodapé (item 5) | 0 elididos a 1920/1366/1280 | `c7_rodape_elisao.py` do ciclo 7, sem alteração: **`dado=313 px, inteiro pede 313 px`, 0 ELIDE** nas três | **CONFIRMADO** |
| Ícones (item 6) | 0 glifos, caixa 16×16, amplitude 0 px | `c7_icones_da_janela.py` do ciclo 7, sem alteração: **0 glifos** (eram 11). Caixa única, amplitude 0 | **CONFIRMADO — mas a régua não vê botão com ícone E texto; §4.3** |
| FEN (item 3) | 48 medições, 0 cortes silenciosos | **48 medições minhas em 3 estados que ele não amostra** (cursor 0, cursor no fim, fonte +3 sem `resize`): **0 cortes silenciosos** | **CONFIRMADO — com a ressalva do §4.4** |
| Rótulos repetidos (item 8) | 3 → 2, os 2 na pele Foco | `c7_rotulos_repetidos.py`, sem alteração: **2 pares divergentes, os dois na Foco**; e o clique na pílula viva devolve mensagem acionável | **CONFIRMADO** |
| Aspas (item 9) | 3 de 3 tipográficas | 3 de 3 no literal, **e 0 de 864 strings desenhadas** com qualquer das 5 faltas tipográficas | **CONFIRMADO E ALARGADO** |
| Piso da janela (item 10) | 1066×735, 0 fora | `minimumSize` **1066×735**; pedi 1024×768, 900×700 e 800×600 → devolve **1066×734**, **0 fora** | **CONFIRMADO** |
| Detector de thread (item 4) | 8/8 do crítico, 8/8 da própria | **6/6 (C5), 8/8 (C7) e 8/8 (C8) confirmados. Plantei 8 formas novas: 8 de 8 escapam** — §4.1 | **CONFIRMADO no que ele mediu; a régua continua atrás** |
| Progresso (item 2) | 5 nomes, 1 veredito; `determinado` = faixa medida | **nomes novos (`montante`, `k`, `len(...)`) acusam** — a independência de nome é real. Mas §4.2: uma subtração escapa, uma string acusa, e `determinado` **nunca** diverge de `passa_total` em 7 de 7 | **METADE CONFIRMADA** |
| Atribuição do bloqueio (item 7) | 7 de 7 com cobertura | **7 de 7 com bloco de atribuição e linha `COBERTURA`, de 86,2 % a 135,2 %.** A aba Dataset reproduz **99,3 %** e nomeia `processEvents` | **CONFIRMADO** |
| Contraste WCAG AA | 296 / 218 / **0**, duas peles | **296 / 218 / 0**; menor folga 3,27:1 e 3,03:1 | **CONFIRMADO** |
| **Teclado + nome + papel** | **216 focáveis, 0 sem nome, PASSOU** | `classica` **PASSOU**; `foco` **REPROVOU (2)**; `fita` **REPROVOU (36)** | **REFUTADO — §3** |
| Nada bloqueia > 16 ms | REPROVOU, 7 ops | **REPROVOU, 7 ops nas 3 execuções.** Medianas de 3: abrir PDF **289,0 ms**, aba Dataset **100,7**, p.41 **108,8**, p.42 **104,4**, p.121 **102,9**, rasterizar **74,0**, aba Galeria **28,1** | **CONFIRMADO como reprovação** (números maiores que os dele: máquina carregada) |
| fps ≥ 55 @ p95 | 91,8 mediana | juntos **88,6 · 86,1 · 79,2 → mediana 86,1**; pan 428–589; zoom 61,3–64,6 → mediana **62,3** | **PASSA** (56 % de folga; o zoom sozinho, 13 %) |
| Suíte nossa | 3011 passed, 1 skipped, **1 failed** | **3022 passed, 1 skipped, 0 failed** em 737 s | **CONFIRMADO — e a falha dele não era dele** |
| Suíte do tronco | 4462 passed, 3 failed, 2 skipped, 4401 subtests | **4462 passed, 3 failed, 2 skipped, 4401 subtests** em 306,04 s | **CONFIRMADO campo a campo** |

**Sobre a falha da suíte nossa que o ciclo 8 atribuiu a outra frente:** ela sumiu sem que ninguém
tocasse em `qt/` ou `ui/`, e a contagem subiu de 3011 para **3022** — 11 casos que não são desta
frente. A atribuição estava certa e eu a verifico pelo desaparecimento, não pelo carimbo.

---

## §3 — Defeito bloqueante

### 1. O portão de nome e papel reprova em duas das três peles que o produto oferece, e na `fita` ele reprova pelo defeito do ciclo 1 — que também está desenhado na tela

**Onde.**
`chess_diagram_ocr/qt/fita.py:302 _botao` (produto) e
`caissa/ui/audit/teclado.py` + `benchmarks/reports/ui/c8/c8_icones_da_janela.py` (instrumentos).
Visível em `benchmarks\reports\critique\ui\c9\zfita_1366x768_resultado.png` e nas outras 17
capturas `zfita_*`; recorte ampliado a 6× em `z_fita_navegacao.png`.

**O que.** `qt/fita.py::_botao` faz sempre as duas coisas:

```python
botao = QToolButton(pai)
botao.setText(quebrar_rotulo(registro.no_botao))     # <- sempre
...
if desenho is not None:
    botao.setIcon(desenho)                            # <- desde o ciclo 8, para 6 comandos a mais
```

com `ToolButtonTextBesideIcon`. Para os seis comandos cujo `no_botao` é um **glifo puro**, isso
desenha o ícone **e** o glifo, lado a lado:

```
  nome=''  text()='-'    icone=True    <<< DESENHO + GLIFO
  nome=''  text()='+'    icone=True    <<< DESENHO + GLIFO
  nome=''  text()='◀'    icone=True    <<< DESENHO + GLIFO
  nome=''  text()='▶'    icone=True    <<< DESENHO + GLIFO
  nome=''  text()='|◀'   icone=True    <<< DESENHO + GLIFO
  nome=''  text()='▶|'   icone=True    <<< DESENHO + GLIFO
```

O glifo ao lado do desenho é o **mesmo `◀` de 5×3 px** que o ciclo 7 fotografou e chamou de
*"traço horizontal chato"*, e que o ciclo 8 apagou em todos os outros painéis com
`qt/icones.vestir` — cujo docstring diz, com todas as letras, *"põe o desenho **e apaga o
glifo** — um botão com ícone e glifo desenha os dois lado a lado"*. A fita não passa por
`vestir`.

E `qt/fita.py` **nunca chama `setAccessibleName`** (nem `qt/fila.py`). Só
`qt/painel_do_pdf._botao` chama, e o comentário dele registra por que:

> *"**O nome acessível é o rótulo por extenso, e não o texto do botão** (F9-C2). O crítico do
> ciclo 1 mediu **28 controles que chegavam ao leitor de tela como "-", "+", "|◀" ou ".md"**."*

O conserto foi para a barra do visor. A fita nasceu depois, com o mesmo defeito, e nenhum portão a
olhou.

**Como reproduzir.**

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONPATH=<suite>\src;<tronco>\src
for %%P in (classica foco fita) do (
  set CVOFF_SKIN=%%P
  ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado ^
      --pdf "...\1937 Kemeri.pdf" --saida benchmarks\reports\critique\ui\c9\tmp_fita
)
```

```
  classica  focaveis por aba [24,52,30,39,21,50] = 216   sem sentido  0   PASSOU
  foco      focaveis por aba [28,56,34,43,25,54] = 240   sem sentido  2   REPROVOU
  fita      focaveis por aba [48,76,54,63,45,74] = 360   sem sentido 36   REPROVOU
```

O JSON do próprio portão nomeia os culpados da `fita`, **seis por aba, nas seis abas**:

```json
{"classe":"QToolButton","nome":"-","origem_do_nome":"texto","papel":"Button",
 "alcancado_pelo_tab":true,"posicao_no_tab":14,"motivo":"sem letras"}
{"classe":"QToolButton","nome":"◀","origem_do_nome":"texto","posicao_no_tab":20,"motivo":"sem letras"}
{"classe":"QToolButton","nome":"|◀","origem_do_nome":"texto","posicao_no_tab":22,"motivo":"sem letras"}
```

Os 2 da `foco` são de outra espécie e muito mais leves: `"Próximo diagrama"` aparece duas vezes na
aba Galeria (`motivo: repetido na aba`) — é o item 11, agora pego por este portão também.

Ou, sem rodar nada: abra `benchmarks\reports\critique\ui\c9\zfita_1366x768_resultado.png` e olhe
os quatro últimos botões da segunda fila.

**Por que reprova.**

1. **É o nono instrumento cego desta frente, e é o primeiro cego por *escopo*.** Os oito
   anteriores erraram a **regra** (um nome de variável, uma dica aceita como pixel, um teste que
   monta o caso e verifica o lado errado). Este acerta a regra e mede **um terço da superfície**.
   O relatório publica `PASSOU` sem dizer em que pele — e o mesmo comando, na pele ao lado,
   devolve `REPROVOU`. A carta §6 manda remedir o número do construtor; remedido, ele inverte.

2. **O produto tem o defeito, não só o instrumento.** A carta §3.3, bloco Visual, reprova sozinho
   *"ícones de origens diferentes misturados (peso, estilo, grade)"*. Aqui é pior: **o mesmo
   botão** carrega o desenho novo e o glifo degenerado que o desenho veio substituir. Está em
   **seis** botões, nas **seis** abas, em **todas** as larguras — 18 capturas minhas o mostram.

3. **É um defeito que o usuário encontra, e a dois cliques.** `Ver ▸ Aparência ▸ Fita` está no
   menu vivo (li a lista: `['Clássica', 'Foco', 'Fita']`). Não é uma pele experimental atrás de
   variável de ambiente: é uma das três aparências que o produto oferece, e `provar_as_peles`
   existe justamente para afirmar que as três abrem.

4. **É o defeito nº 1 do ciclo 1 desta frente, vivo.** Vinte e oito controles chegando ao leitor
   de tela como `-`, `+`, `|◀`. O ciclo 2 fechou isso — em `painel_do_pdf`. A fita repõe seis, e
   nenhum dos quatro portões visuais (ícones, vazio de painel, ocupação, rodapé) nem o de teclado
   jamais rodou nela.

**O conserto é duas linhas de produto e um `for` no arnês:**

* **Produto**: em `qt/fita.py::_botao` (e em `qt/fila.py`, pelo mesmo motivo), (a) chamar
  `botao.setAccessibleName(comandos.nome_acessivel(registro.acao))`, que é o que
  `painel_do_pdf._botao` já faz; e (b) **não escrever o glifo quando há desenho** — a regra já
  existe e se chama `qt/icones.vestir`.
* **Arnês**: `caissa.ui.audit.teclado` percorre `ui/pele.PELES` em vez de herdar `CVOFF_SKIN`, e o
  relatório publica uma linha por pele. O mesmo `for` em `c8_icones_da_janela.py` e em
  `capture.PELES`.

*Alvo, cobrado por teste: o portão de teclado devolve `PASSOU` em **cada** pele registrada, com
`0 sem nome, 0 sem papel, 0 nome vazio de sentido`; e `c7_icones_da_janela.py` devolve
`GLIFOS DE TEXTO: 0` em **cada** pele. Prova de vida: apagar o `setAccessibleName` de um botão da
fita faz os dois reprovarem.*

---

## §4 — Defeitos não bloqueantes

Em ordem de custo, com a medida de cada um.

### 4.1 O detector de thread: oito formas novas, oito escapam — e o problema já não é a lista

O alvo dos ciclos 5, 6 e 7 está batido e eu o confirmo nas três árvores intocadas: **6/6 (C5),
8/8 (C7), 8/8 (C8)**. E o tronco real está limpo: 13 operações de fundo em `qt/`, 0 invisíveis, e
eu varri `qt/` e `ui/` procurando as minhas oito formas — **nenhuma existe hoje**.

Plantei oito que nenhuma das quatro sabotagens anteriores tem
(`benchmarks\reports\critique\ui\c9\sab_c9\`):

| forma | resultado |
|---|---|
| (a) `fabrica_de_thread()(target=…)` — a **classe devolvida** por uma função | **escapa** |
| (b) `if (Fabrica := threading.Thread)` — apelido por **walrus** (`ast.NamedExpr`) | **escapa** |
| (c) `Primaria, Secundaria = threading.Thread, threading.Timer` — alvo `ast.Tuple` | **escapa** |
| (d) `fabrica: type = threading.Thread` num **campo anotado** de `dataclass` (`ast.AnnAssign`) | **escapa** |
| (e) `QProcess.startDetached(prog, args)` — o jeito canônico do Qt | **escapa** |
| (f) `QtConcurrent.run(...)` — vindo do binding, sem corpo Python para ler | **escapa** |
| (g) `@em_fundo` — decorador que mora **noutro módulo** | **escapa** (só o ajudante é nomeado) |
| (h) `type("Fundo", (threading.Thread,), {})()` — subclasse em tempo de execução | **escapa** |

```
Operacoes de fundo em qt/ (1)
  INVISIVEL (constroi threading.Thread) (modulo).dentro   ajudante_de_fundo.py:18
DEFEITOS BLOQUEANTES (1)
```

**Uma linha, e ela nomeia um ajudante noutro arquivo — nenhum dos oito métodos que abrem trabalho
é nomeado.** Os quatro controles negativos (`self._relogio.start(250)`, `list(map(str, …))`,
`partial(self._ir, 1)`, `acoes["ir"](2)`) ficaram mudos, então o detector também não passou a
gritar.

**O que isto quer dizer, e não é "acrescente mais oito nomes".** A régua é AST e sintática; a
progressão 1/6 → 6/6 → 8/8 → 8/8 → **0/8** mostra que cada rodada fecha as formas da rodada
anterior e a seguinte inventa outras. *Alvo, e ele é de forma e não de lista: um portão de
**execução** — a suíte Qt conta `threading.enumerate()` antes e depois de cada ação e exige que
toda thread nova esteja no `BusyRegistry` ou em `FORA_DO_REGISTRO`. Uma thread que corre é
observável; uma que a AST não escreveu, não. A sabotagem C9 fica no repositório do arnês como a
C5, a C7 e a C8 ficaram.*

### 4.2 "Total conhecido" já não depende do nome — mas depende de a expressão ser uma chamada, e "determinada" é uma consulta de duas entradas

**A metade boa é real e eu a verifiquei com formas que nenhum dos dois usou**
(`sab_c9_prog\`, oito registros):

```
  p1  montante = self.contagem_de_amostras()  -> detail f"{montante} amostra(s)"   ACUSA  ok
  p2  k = self.contagem_de_amostras()         -> detail f"{k} linha(s)"            ACUSA  ok
  p3  detail f"{len(self.linhas())} linha(s)"                                      ACUSA  ok
  n1  motor = self._motor (atributo LIDO)     -> detail f"motor {motor}"           calado ok
```

O defeito do ciclo 7 — *"renomeie uma variável e o portão inverte o veredito"* — está morto.

**As duas bordas, medidas:**

```
  p4  parcial = self.contagem_de_amostras(); restante = parcial - 1
      -> detail f"{restante} a ler"                     NAO ACUSA   <<< uma subtracao e ele perde
  n2  nome = self.nome_do_livro()  (devolve STRING)
      -> detail f"lendo {nome}"                         ACUSA       <<< falso positivo
```

A regra trocou "o nome da variável" por "o valor veio de uma chamada", e erra nos dois sentidos.

**E a segunda metade — "`determinado` é a faixa medida do widget" — é mais fina do que o relatório
sugere.** `auditar()` chama `faixas_medidas()`, que mede a faixa **exatamente duas vezes**
(`total=289` e `total=0`) e depois resolve `determinado` por consulta a esse par, com chave
`passa_total`. Consequência, medida nas 7 operações reais:

```
  7 registros; 0 em que 'passa_total' e 'determinado' divergem
```

A coluna que o relatório apresenta como medida carrega exatamente a mesma informação que a coluna
lida do código. E ela é derrubada por um tique
(`c9_faixa_tardia.py`, sabotando `RodapeDaJanela._trocar_modo_da_barra`):

```
  faixa que chega TARDE (QTimer.singleShot(40, ...)):  total=289 -> (0,100)  ->  0 operacoes acusadas
  faixa que RECUA depois de lida:                      total=289 -> (0,100)  ->  0 operacoes acusadas
```

Porque `RodapeDaJanela.__init__` já põe `setRange(0, 100)` (linha 158): a sonda lê o estado
**inicial** do widget, não o que a operação produz. É literalmente o cenário que o docstring da
função declara querer impedir — *"bastaria `qt/rodape.py` deixar de trocar de modo para o portão
continuar verde com a barra andando"*. **Hoje o produto troca o modo de forma síncrona e o número
publicado está certo**; o que não segura é a régua. *Alvo: medir a faixa **por operação**, depois
de aplicar aquela ocupação, e comparar com a faixa de repouso — não uma consulta de duas
entradas.*

**Nota de bônus.** A única não‑determinação que sobrou nas 36 capturas é a fase desta marquise
(§2, primeira linha). O item que o portão declara aberto é o único que faz o arnês não ser
bit‑a‑bit reprodutível.

### 4.3 O censo de ícones não vê nenhum botão que tenha ícone **e** texto

`c8_icones_da_janela.py`, a régua com que "18 botões, caixa única 16×16, amplitude 0 px" é
publicado, filtra `if tem_icone and not texto`. Os **três** botões com ícone e texto da janela
foram criados neste ciclo — incluindo o `OCR todos diagramas` que fecha o bloqueante — e nenhuma
régua os mede. Incluí‑los não piora o número (§1, critério 3), e é por isso que isto é não
bloqueante; mas a régua ficou cega justamente para a família nova. *Alvo: o filtro passa a ser
`if tem_icone`, e o relatório publica as duas famílias separadas.*

### 4.4 A marca da FEN aponta para o lado errado no estado em que o usuário a produz

O conserto é bom e eu o ataquei em dois estados que a régua do construtor não amostra
(`c9_fen_estados.py`, **48 casos, 0 cortes silenciosos**), inclusive **fonte +3 sem `setText` e
sem `resize`** — o `resizeEvent` re‑arma a marca, e ela acende.

Mas `c8_fen_avisa.py` faz sempre `setText(fen)` seguido de `setCursorPosition(0)`: é o estado de
quem **recebe** uma FEN do programa. Quem **digita ou cola** fica com o cursor no fim:

```
  1280 [Estudo] cursor no fim: marca=13 px, ultimo caractere visivel (indice 72)
```

O último caractere não some — a marca não o come, e eu me enganei ao supor que sim. O que
acontece é outra coisa, e está na foto `z_fen_cursor_fim.png`: o campo mostra
`…129 …` — **a reticência à direita, depois do último caractere**, enquanto o texto escondido
está à **esquerda**, onde não há marca nenhuma e um glifo aparece cortado ao meio. Quem cola uma
FEN e lê `129 …` conclui que a colagem foi truncada no fim. *Alvo: a marca vai para o lado em que
há texto fora — os dois lados, quando os dois estão.*

### 4.5 "Motivo" ilegível em 17 de 27 linhas a 1920 e 25 de 27 a 1280

Reproduzido com o instrumento do construtor, sem alterá‑lo:

```
  1920: coluna 'Motivo' com 702 px -> 17 de 27 linhas nao cabem
  1366: 388 px -> 24 de 27
  1280: 339 px -> 25 de 27
```

(O relatório diz 19 de 27 a 1920; eu meço 17. A diferença é de estado de fila, não de leiaute.)

**Menos grave do que o ciclo 7 afirmou, e digo por quê:** existe `lbl_motivo` sob a tabela, que
mostra o motivo **inteiro** do item selecionado (`painel_de_revisao.py:246`, S‑153), e a primeira
oração — a que classifica (`ilegal: falta o rei preto`, `orientação incerta: margem apertada`,
`confiança mínima 0.002 < 0.80`) — cabe em **27 de 27**. O que se perde é a cauda. *Alvo continua:
0 de 27 pedindo mais largura, com quebra em duas linhas; há 394,0 kpx de tabela vazia logo abaixo.*

### 4.6 O estado desabilitado, na pele Foco, custa 1,88:1 — e o próprio produto usa 3,0:1 como piso

Medido no §1, critério 7. Face 1,22:1, tinta 1,88:1, e **22 de 22 rótulos mortos com contraste
igual ou maior que o rótulo vivo mais fraco**. Nenhum portão cobre isto: o de contraste mede
`:disabled` e o declara **isento** (WCAG 1.4.3/1.4.11, e a isenção está certa para
acessibilidade), e o `c7_estados_do_botao.py` mede *quantos pixels mudam*, que não é *o quanto*.
*Alvo: a distância vivo↔morto entra no portão de contraste como par próprio, com piso 3,0:1 — o
mesmo que o produto já aplica a uma listra de tabela.*

### 4.7 Órfãs em 8 de 54 parágrafos, e a pior é a primeira frase do produto

Medido no §1, critério 6. `'inteira.'` sozinha numa linha de 627 px de medida (**5,7 %**), na
`MENSAGEM_VAZIA`. *Alvo: nenhuma última linha com uma palavra só; o conserto é um espaço
inquebrável antes da última palavra.*

### 4.8 A Estudo piora com a tela

281,5 kpx de vazio a 1920, **593,9 a 2560, 1 569,6 a 3840**. Medido no §1, critério 4. É a metade
do §3.2 da carta que oito ciclos não rodaram. *Alvo: o painel da Estudo redistribui a sobra acima
de 1920 em vez de a deixar entre o tabuleiro e a coluna de lances.*

### 4.9 O que continua aberto e declarado, e eu confirmo o número

* **Bloqueio > 16 ms**: REPROVA, 7 operações, mediana da pior **289,0 ms** (11,3× o orçamento).
  A parte desta frente é 1,5 %–2,0 %, e eu confirmo. A E/S de disco na thread da janela é real e
  a pilha do pior nomeia **um caminho que o relatório não cita**:
  `estudo_arquivo.py:85 chave_de → pathlib.resolve → ntpath.realpath`, ao lado dos dois
  declarados (`marcas.py:77 _marca_de`, `painel_da_galeria.py:1087 _abrir_cache_de_posicoes`).
  Na minha execução `sqlite3.Connection.execute` custa **36,5 ms** dos 227.
* **Item 6** (vazio de painel): 10 de 12 acima de 200 kpx a 1920. Honestamente aberto.
* **Item 7** (poço à direita da paleta): 114,5 kpx a 0,00 % de tinta. Honestamente aberto — e o
  construtor publicou o número que **piorou** (109,7 → 114,5) em vez do que melhorou.
* **Item 10** (piso 1066×735): honestamente aberto, com a frase inteira ("num monitor de 1024×768
  a janela transborda 42 px").
* **Tinta dos ícones** 17,6 %–41,4 %: honestamente aberto, com o motivo de desenho declarado.
* **Item 8** (2 `Cancelar`/pílulas divergentes): honestamente aberto, e menos grave do que
  parecia — o clique responde `"Não há diagrama lido para salvar: leia uma página antes."`

**Nenhum dos seis é "convenientemente aberto".** Em todos, o número publicado é o que eu meço, e
em dois deles (item 7 e a barra do dataset) o construtor escolheu publicar o lado que o
desfavorece. Isso é o comportamento que a carta pede.

### 4.10 Miudezas medidas

* `nomear_o_que_o_cromo_nao_desenha` não pergunta `isVisible()` (§1, critério 8, caso 5).
* Duas linguagens de seta e 1,9× de massa no paginador de quatro botões da Galeria.
* Casas de **72,125 px** no tabuleiro da Estudo a 1920 (577/8).
* `outro` em caixa baixa entre oito *tags* PGN capitalizadas (as *tags* em inglês estão
  justificadas: são o formato do arquivo).
* `peças ainda não · texto desligado` no rodapé: a zona de dispositivos imprime uma oração
  incompleta. É `estado_do_rodape.SEM_MODELO`, e a escolha está documentada — mas na tela lê‑se
  como frase cortada.
* Dois destrutivos vermelhos lado a lado na Estudo (`Apagar variante`, `Apagar daqui`).
* `zoom` é o gesto apertado do portão de quadros: mediana de 3 execuções **62,3 fps @ p95** contra
  o piso de 55 — 13 % de folga, contra 56 % do conjunto.

---

## §5 — O que este ciclo conquistou, e eu confirmo com número

Não estou dando crédito por esforço. Registro o que remedi e bateu.

1. **A autodenúncia do arnês é verdadeira, e eu a testei do jeito mais duro que consegui.**
   Envenenei `sash_fraction` para **0,20** e para **0,90**, mais a página, o zoom, a geometria, a
   aba ativa e o divisor da Estudo, e capturei as 36 duas vezes. **Toda diferença cabe numa caixa
   de 118×24 px do rodapé** — a fase da marquise. A linha central das capturas é idêntica; o
   divisor cai em **x=1073** nas duas. E, contra o conjunto **publicado** pelo construtor, 17 de
   36 são idênticas byte a byte e as 19 restantes diferem só na mesma caixa. **O número do §6 é o
   honesto, e ele é reprodutível a partir de um estado sujo.**

2. **O bloqueante do ciclo 7 está morto e o desenho que o matou é o certo.** Ler o `text()` do
   cromo em vez de consultar uma tabela é a decisão que não driftaria no dia em que alguém
   demovesse um comando — e eu testei essa exata hipótese em seis cromos, inclusive o que a ordem
   de serviço pediu (**o nome só dentro de um menu**): a barra nomeia, que é a resposta certa.

3. **A independência de nome de variável é real**, e eu a provei com nomes e formas que nenhuma
   das duas rodadas usou (`montante`, `k`, `len(...)` direto).

4. **Sete de sete operações do portão de bloqueio têm atribuição com cobertura**, de 86,2 % a
   135,2 %, e a aba Dataset — que o ciclo 7 mostrou reproduzida a 1,9 % — agora reproduz **99,3 %**
   e nomeia o que trava (`processEvents`, o Qt montando a aba pela primeira vez).

5. **Onze glifos de texto viraram zero na pele padrão**, com caixa única de 16×16 e amplitude
   0 px, confirmado com o instrumento do ciclo 7 sem tocá‑lo.

6. **Zero faltas tipográficas em 864 strings desenhadas**, nas três peles — mais do que o
   construtor afirmou.

7. **Nada foi afrouxado.** A suíte nossa passa **3022** com **0 reprovados** (e a única falha do
   ciclo 8 sumiu sem que esta frente tocasse no arquivo, o que confirma a atribuição dele); a do
   tronco fecha **campo a campo**, com as três reprovações pré‑existentes de sempre. A catraca de
   `qt/janela.py` subiu **uma** linha, com o motivo escrito no formato das entradas anteriores.

8. **A disciplina de caminho de saída foi respeitada dos dois lados.** Nenhuma captura foi perdida
   neste ciclo, e as duas armadilhas que encontrei (`c7_zoom.py` grava na pasta do c7,
   `c7_cor_e_bordas.py` lê da pasta do c6) foram desarmadas antes de rodar.

---

## §6 — O que especificamente precisa mudar para eu aprovar

**Um item bloqueia. Só ele.**

1. **Faça a pele `fita` deixar de desenhar o glifo ao lado do ícone, dê nome acessível aos
   botões do cromo, e faça os portões rodarem nas três peles.** Três metades, as três
   obrigatórias:
   - **Produto (a)**: `qt/fita.py::_botao` — quando `registro.icone` produz desenho, **não**
     escrever o glifo. A regra já existe: `qt/icones.vestir` (*"põe o desenho e apaga o glifo"*).
     Hoje seis botões desenham os dois: `-`, `+`, `◀`, `▶`, `|◀`, `▶|`.
   - **Produto (b)**: `qt/fita.py::_botao` e `qt/fila.py` chamam
     `setAccessibleName(comandos.nome_acessivel(acao))`, que é o que `painel_do_pdf._botao` já
     faz desde o ciclo 2. Hoje seis controles chegam ao leitor de tela como o glifo, em **cada uma
     das seis abas** — 36 ocorrências.
   - **Portão**: `caissa.ui.audit.teclado` percorre `ui/pele.PELES` e publica **uma linha por
     pele**; o mesmo `for` em `c8_icones_da_janela.py` e em `capture.PELES`.

   *Alvo, cobrado por teste: o portão de teclado devolve `PASSOU` em cada pele registrada
   (`0 sem nome, 0 sem papel, 0 nome vazio de sentido`) e `c7_icones_da_janela.py` devolve
   `GLIFOS DE TEXTO: 0` em cada pele. Prova de vida: apagar um `setAccessibleName` da fita, ou
   repor um `setText` de glifo num botão com ícone, faz os dois reprovarem — hoje os dois passam
   porque não olham.*

**Não bloqueiam, e entram no §9 da próxima ordem de serviço nesta ordem:**

2. **Fotografe a `fita` e meça o §3.2 inteiro.** `capture.PELES` vai a três; `TAMANHOS` ganha
   3840×2160. *Alvo: 54 capturas, e o item 6 medido nas três peles e em quatro tamanhos.*
3. **A Estudo redistribui a sobra acima de 1920.** *Alvo: o maior vazio do painel não cresce com a
   janela — hoje 281,5 kpx a 1920, 593,9 a 2560 e **1 569,6 a 3840**.*
4. **O estado morto passa a custar 3,0:1.** *Alvo: a distância vivo↔morto (tinta do rótulo) entra
   no portão de contraste como par próprio, com o mesmo piso de 3,0:1 que o produto já aplica a
   uma listra. Hoje: 2,82:1 na clássica e **1,88:1** na Foco, com 22 de 22 rótulos mortos mais
   legíveis que o vivo mais fraco.*
5. **Troque a régua do detector de thread por uma de execução.** *Alvo: a suíte Qt conta
   `threading.enumerate()` antes e depois de cada ação e exige registro ou declaração; a
   sabotagem C9 (8 formas, 4 controles negativos) entra no repositório e as 8 passam a ser
   pegas. Hoje 8 de 8 escapam.*
6. **`determinado` medido por operação.** *Alvo: adiar `_trocar_modo_da_barra` por um tique não
   apaga o defeito — hoje apaga, e o portão deixa de acusar qualquer coisa.* E a heurística de
   contagem para de perder uma subtração (`restante = parcial - 1`) e de acusar uma string
   (`nome = self.nome_do_livro()`).
7. **A marca da FEN vai para o lado em que há texto fora.** *Alvo: com o cursor no fim, a marca
   está à esquerda; com os dois lados fora, nos dois.*
8. **O censo de ícones inclui os botões com ícone e texto** (`if tem_icone`), e o paginador de
   quatro botões usa **uma** linguagem de seta. *Alvo: massa de tinta dentro de ±20 % entre irmãos
   do mesmo grupo — hoje 45..87 px², 1,9×.*
9. **`Motivo` legível**: 0 de 27 pedindo mais largura, nas três larguras. Há 394,0 kpx de tabela
   vazia logo abaixo.
10. **Órfãs**: 0 de 54 parágrafos com a última linha de uma palavra. Comece por `'inteira.'`, que
    é 5,7 % de uma medida de 627 px na primeira frase que o produto mostra.
11. **Um rótulo, um controle**: os 2 pares divergentes da pele Foco; e `Próximo diagrama` duas
    vezes na Galeria, que o portão de teclado já acusa.
12. **Itens 6, 7, 10, a tinta dos ícones e o bloqueio > 16 ms** continuam abertos com os números
    de sempre, e continuam declarados sem atenuação. Nenhum deles precisa fechar para eu aprovar.

---

## §7 — Como reproduzir

```bat
:: portoes -- --saida SEMPRE para a pasta do critico
sh benchmarks\reports\critique\ui\c9\c9_portoes.sh     :: contraste, progresso, teclado, bloqueio x3, quadros x3
.venv\Scripts\python.exe -m pytest tests -q            :: 3022 passed, 1 skipped, 0 failed
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly   :: no tronco

:: o BLOQUEANTE -- o mesmo portao, uma pele de cada vez
for %%P in (classica foco fita) do (set CVOFF_SKIN=%%P & ^
  ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado ^
      --pdf "...\1937 Kemeri.pdf" --saida benchmarks\reports\critique\ui\c9\tmp_fita)
   :: classica PASSOU (0) | foco REPROVOU (2) | fita REPROVOU (36)

:: determinismo do arnes (envenena data/app_tkinter_state.json e RESTAURA)
sh benchmarks\reports\critique\ui\c9\c9_determinismo.sh 0.20 capA
sh benchmarks\reports\critique\ui\c9\c9_determinismo.sh 0.90 capB
   :: 24/36 diferem, e so numa caixa de 118x24 px do rodape (a fase da marquise)

:: sabotagens (nenhuma escreve sobre o tronco nem sobre as capturas)
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco ...\c9\sab_c9      --saida ...\c9\tmp_sab  :: 0 de 8
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco ...\c9\sab_c9_prog --saida ...\c9\tmp_sab  :: p1-p3 acusam, p4 escapa, n2 falso
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco ...\critique\ui\c5\sabotado --saida <tmp>  :: 6 de 6
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco ...\critique\ui\c7\sab_c7   --saida <tmp>  :: 8 de 8
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco ...\reports\ui\c8\sab_c8    --saida <tmp>  :: 8 de 8

:: instrumentos deste ciclo (benchmarks\reports\critique\ui\c9\ -- so c9_zoom, c9_quatro_k,
:: c9_pele_fita e c9_fen_foto gravam, e gravam aqui)
c9_vazio_no_piso.py        :: 3 peles x 4 larguras: 0 nao desenhados, 0 duplicados
c9_cromo_menu.py           :: menu ok, botao escondido ERRADO
c9_fen_estados.py          :: 48 casos em 3 estados, 0 cortes silenciosos
c9_faixa_tardia.py         :: 'determinado' nunca diverge de 'passa_total'; um tique apaga o portao
c9_icones_com_texto.py     :: 18 so-de-icone + 3 COM TEXTO (fora da regua do c8)
c9_tipografia_na_tela.py   :: 864 strings, 0 faltas
c9_estado_morto.py         :: face 1.10/1.22:1, tinta 2.82/1.88:1
c9_orfas.py                :: 8 de 54 parágrafos com orfa
c9_quatro_k.py             :: Estudo 281,5 -> 593,9 -> 1569,6 kpx
c9_pele_fita.py            :: as 18 capturas da terceira pele
c9_zoom.py <png> x0 y0 x1 y1 [fator] [nome]

:: instrumentos anteriores, rodados sem alteracao (conferido antes que nao gravam)
critique\ui\c7\c7_icones_da_janela.py   :: 0 glifos (eram 11)
critique\ui\c7\c7_rodape_elisao.py      :: 0 ELIDE nas tres larguras
critique\ui\c7\c7_rotulos_repetidos.py  :: 2 pares divergentes
critique\ui\c7\c7_janela_pequena.py     :: minimumSize 1066x735, 0 fora
critique\ui\c5\c5_vazios.py  <png..>    :: 10 de 12 acima de 200 kpx a 1920
critique\ui\c5\c5_regioes.py <png..>    :: 73,1 %, vao 16 px, 114,5 kpx
ui\c8\c8_vazio_na_tela.py               :: 30 de 30 DESENHADO=sim
ui\c6\c6_aberto.py                      :: 29 botoes em 4-6 filas; Motivo 17/24/25 de 27
:: NAO rodei: c7_zoom.py (grava na pasta do c7). NAO confiei em: c7_cor_e_bordas.py (le da pasta do c6).
```

Artefatos meus, todos em `benchmarks\reports\critique\ui\c9\`: `capA\` e `capB\` (36 capturas cada),
`zfita_*` (18), `z4k_*` (8), as árvores `sab_c9\` e `sab_c9_prog\`, os doze instrumentos,
`bloqueio_run{1,2,3}.txt`, `quadros_run{1,2,3}.txt`, `contraste.txt`, `progresso.txt`,
`teclado.txt`, `suite_nossa.txt`, `tronco.txt`, os JSON dos portões, os recortes `z_*.png` e
`BACKUP_app_tkinter_state.json` (o estado do tronco, restaurado e conferido campo a campo).
**Nada fora desta pasta e deste documento foi escrito por mim.**

---

## §8 — Veredito

**REPROVADO — por um defeito, e ele é uma pele que nenhum instrumento desta frente jamais olhou.**

Este é o ciclo em que quase tudo fechou. O bloqueante do ciclo 7 está morto e o desenho que o
matou é o certo — eu o ataquei em seis cromos, inclusive o do menu que a ordem de serviço pediu, e
ele responde bem em cinco. O rodapé não elide mais. A FEN avisa, e avisa também nos dois estados
que a régua do construtor não amostra. Os onze glifos de texto viraram zero na pele padrão. As
sete operações do portão de bloqueio têm atribuição com cobertura, e a que ninguém conseguia
explicar agora reproduz 99,3 %. A tipografia da tela inteira — 864 strings, três peles — não tem
uma falta. As duas suítes fecham, com **0 reprovações** na nossa.

E **a autodenúncia do arnês é verdadeira**: capturei as 36 duas vezes a partir de estados de
sessão opostos e envenenados, e a única diferença que existe cabe numa caixa de 118×24 px — a
fase da marquise, que é o próprio item que o relatório declara aberto. Contra o conjunto
publicado, 17 de 36 são idênticas byte a byte. **O construtor pegou o artefato que o favorecia,
publicou o número que não o favorecia, e o número resiste a quem tenta quebrá‑lo.** Isso é o
comportamento que queremos e eu digo isso com a medida na mão.

Não aprovo porque o portão que o relatório publica como **PASSOU** devolve **REPROVOU** em duas
das três peles que o produto oferece no menu — e na terceira, a `fita`, ele acusa **36
ocorrências** do defeito nº 1 do **ciclo 1** desta frente: controles que chegam ao leitor de tela
como `-`, `+`, `◀`, `▶`, `|◀`, `▶|`. Não é só o instrumento: **os mesmos seis botões desenham o
ícone novo e o glifo velho lado a lado**, e o glifo velho é o `◀` de 5×3 px que o ciclo 7 mediu e
o ciclo 8 apagou em todo lugar menos ali.

Os oito instrumentos cegos anteriores erraram a **regra**. Este acerta a regra e mede **um terço
da superfície** — é a primeira cegueira de escopo, e ela custou o menor número de linhas de todas:
um `for` sobre `ui/pele.PELES`. Feito o item 1 do §6 — o glifo que sai, o nome acessível que
entra, e os portões percorrendo as três peles —, **aprovo**. Os onze itens restantes são desenho,
medida e disciplina de instrumento; nenhum deles põe na tela um controle sem nome.
