# F9 — Interface, crítica do ciclo 11

```
VEREDITO: REPROVADO
CICLO: 11
FRENTE: F9 (Interface)
```

**O bloqueante do ciclo 9 morreu, e morreu bem.** Remedi as três metades que a ordem de serviço
exigiu e as três batem: o portão de teclado devolve **PASSOU nas três peles** (216 / 240 / 360
focáveis, `0 sem nome, 0 sem papel, 0 nome vazio, 0 fora do Tab`), o censo devolve
**`GLIFOS DE TEXTO em TODAS as peles: 0`**, e a guarda de largura é **estrutural e eu a testei por
mutação, não por leitura**: registrei uma quarta pele em `ui/pele.PELES` e o portão passou a
percorrê‑la sozinho; tirei a `fita` de `capture.PELES` e o teste caiu; tirei o 4K de `TAMANHOS` e
caiu também. A prova de vida fecha nos dois sentidos com os números exatos do relatório — 90
acusados sem `setAccessibleName`, 6 glifos com o glifo de volta, `qt/fita.py` restaurado com
`sha256 = 1f27fac6…4a`.

**Reprova por uma coisa, e ela é o décimo instrumento cego — o segundo cego por escopo.**

O portão que publica `0 sem nome` percorre `janela.abas`: as **seis abas da janela principal**. O
produto tem **doze `QDialog`**, e em onze ciclos nenhum portão desta frente jamais abriu um. Rodei
a régua **do próprio portão**, sem alterar uma linha, em seis diálogos que o usuário alcança pelo
menu e por atalho:

```
  JanelaDaPaleta      (Ctrl+Shift+P)        2 focáveis   2 SEM NOME
  JanelaDeBusca       (Achar no texto…)     5 focáveis   2 SEM NOME
  JanelaDeBusca       (substituindo)        7 focáveis   3 SEM NOME
  JanelaDeAtalhos     (Ver ▸ Atalhos)       2 focáveis   1 SEM NOME + 1 SEM PAPEL
  JanelaDeEstatisticas(Dataset)             1 focável    1 SEM NOME
  _JanelaDeColar      (Estudo ▸ Colar)      3 focáveis   1 SEM NOME
  --------------------------------------------------------------------
  11 defeitos, pela régua que publica "0 sem nome" na janela principal
```

Na janela principal, a mesma régua acha **11 `QLineEdit`, 1 `QTextBrowser` e 3 `QTextEdit` com
0 sem nome**. Nos diálogos, o campo onde se digita o comando na **paleta de comandos** — a
superfície que existe *para quem usa o teclado*, aberta por `Ctrl+Shift+P` — chega ao leitor de
tela sem nome nenhum; e em `Achar e substituir` são **dois `QLineEdit` sem nome lado a lado**, de
modo que quem não vê a tela não distingue "Achar" de "Trocar por".

E o produto **já tem o remédio**, com a decisão tomada e escrita: `qt/acessibilidade.nomear_tudo`,
cujo docstring diz *"Dá nome acessível a todo controle da janela que ainda não tem um"* e
*"a vigésima primeira — o campo que o próximo item acrescenta — nasceria muda"*. Ele é chamado
**uma vez em todo o produto**, em `qt/janela.py:361`, sobre a janela principal, dentro do
`__init__` — e **todo diálogo é construído depois**. Chamei‑o à mão em cada um dos seis:

```
  DEFEITOS nos 6 dialogos:  antes = 11   depois de nomear_tudo = 0
      derivado: QLineEdit -> 'Achar'          QLineEdit -> 'Trocar por'
      derivado: QScrollArea -> 'Atalhos de teclado'   TabelaQt -> 'Tabela de resultados'
```

É o defeito nº 1 do **ciclo 1** desta frente, vivo, na parte do produto que nenhum portão desta
frente olhou — e a varredura que existe exatamente para impedi‑lo nunca correu ali.

---

## Nota de procedimento

Rodei tudo do zero. **Conferi o destino de cada script antes de rodá‑lo**, e registro a falta que
cometi assim mesmo:

* `caissa.ui.audit.execucao` tem `--saida` com **padrão em `benchmarks\reports\ui\`** — a pasta do
  construtor. Rodei a minha sabotagem sem `--saida` e ela gravou
  `execucao_sab_sab_c11_20260909_224629.json` lá. **Movi o arquivo para
  `benchmarks\reports\critique\ui\c11\gates\`** assim que vi; `find benchmarks\reports\ui
  -maxdepth 1 -newermt "22:00"` devolve **0 arquivos**. Nas demais invocações passei `--saida`.
  Fica o aviso para quem vier: o padrão do módulo aponta para a pasta que o crítico não pode tocar.
* `benchmarks\reports\ui\c10\c10_prova_de_vida.py` e `c10_faixa_tardia.py` **editam arquivos do
  tronco** (`qt/fita.py`, `qt/rodape.py`) e os restauram. Registrei o SHA‑256 dos dois **antes**
  (`1f27fac6…4a` e `8f45d98e…26`), rodei, e os dois voltaram idênticos — conferido por mim, não
  pela palavra do script.
* Os instrumentos `c5_*`, `c6_aberto.py`, `c7_*`, `c9_tipografia_na_tela.py` não gravam nada
  (conferido por busca de `write_text`/`save`/`json.dump`/`open(...,'w')` antes de cada um).
  `c6_aberto.py` escreve `capture_estado.json` em `tempfile.mkdtemp()`, fora do repositório.
* **`data/janela.json` do tronco**, que é o estado da janela **Qt** (`qt/janela.py:178`), **é
  reescrito pelo portão de bloqueio** — ele constrói `JanelaPrincipal()` sem
  `caminho_do_estado`. Copiei‑o para `c11\BACKUP_janela.json` com SHA‑256 assim que descobri,
  envenenei‑o para medir se o número depende dele (não depende — §5.5), e restaurei: `sha256
  77d24622…cd`, **campo a campo idêntico**. O que **não** consigo desfazer é a reescrita das minhas
  três primeiras execuções do `bloqueio`, feitas antes de eu saber que ele escreve ali — e é por
  isso que o item existe.
* Exportei `PYTHONDONTWRITEBYTECODE=1` em toda invocação.
* **Nada foi escrito fora de `docs\quality\F9_CRITIQUE_C11.md` e de
  `benchmarks\reports\critique\ui\c11\`**, com as duas exceções declaradas acima. O
  `data/app_tkinter_state.json` do tronco continua com `mtime` **13:25** — os portões passam por
  `capture.estado_de_medicao(pasta)` desde o ciclo 10 e isso segura. Só que esse não é o arquivo da
  janela Qt (§5.5).

Instrumentos meus, todos em `benchmarks\reports\critique\ui\c11\`, nenhum grava fora dela:

| instrumento | o que responde |
|---|---|
| `c11_dialogos.py` / `c11_dialogos2.py` | a régua do portão de teclado aplicada aos diálogos |
| `c11_dialogos_prova.py` | **`nomear_tudo` num diálogo: 11 → 0** — a prova de que o remédio é do produto |
| `c11_dialogos_censo.py` | os 12 `QDialog`, e quantos `setAccessibleName` cada arquivo tem |
| `c11_largura_da_medicao.py` | uma **quarta pele** alcança o portão? e o eixo **densidade**? |
| `c11_guarda.py` | mutação: tirar a `fita` de `capture.PELES` faz o teste cair? |
| `c11_glifo_em_qualquer_lugar.py` | glifo fora de `QAbstractButton` — rótulo, cabeçalho, item, menu |
| `c11_texto_cortado.py` | **régua nova**: todo widget com texto, 3 peles × 3 larguras |
| `c11_ritmo_da_fita.py` / `c11_alinhamento_da_fita.py` | a geometria exata dos 24 botões da fita |
| `c11_faixa_250ms.py` | `determinado` sob um tique **maior** que `ASSENTAR_MS` |
| `sab_c11/` | 4 formas de operação de fundo contra a **fronteira de mecanismo** |
| `c11_cor_no_cromo.py` | o censo de matiz, agora também na `fita` |
| `c11_casas_do_tabuleiro.py` / `c11_casas_no_pixel.py` | o lado da casa fecha num inteiro? |
| `BACKUP_janela.json` + `sha_janela_antes.txt` | o estado Qt do tronco, envenenado e restaurado |

**Uma vez o meu olho errou e a régua acertou**, e registro: no recorte a 3× da fita achei que as
duas linguagens de seta do paginador estavam misturadas outra vez. Não estão — o item usa
*chevron* (`<`, `>`) e a página usa *triângulo* (`◁`, `▷`), que é exatamente a regra que o ciclo 8
declarou. A régua é a favor do construtor e eu digo isso.

---

## §1 — Comparação às cegas (substituição do §2.1)

Mantida a substituição das rodadas anteriores: os **nove critérios de desenho**, cada um com a
pergunta *"isto sobrevive ao lado do Affinity Publisher, do Chessbase 17 e do Scrivener?"*, e a
medida que sustenta a resposta.

### 1. Hierarquia visual — **SOBREVIVE na clássica e na Foco; a `fita` entrega metade do que ela mesma promete**

O estado vazio nomeia o comando em **36 de 36** linhas (3 peles × 4 larguras × 3 nomes), com
`0 não desenhados, 0 duplicados`, e o método agora pergunta `isVisibleTo(cromo)`. Confirmado com o
instrumento do construtor e com o do ciclo 8 sem alteração (`30 de 30 DESENHADO=sim`).

O que **não** fecha é a `fita`, e a acusação vem da declaração do próprio produto.
`ui/pele.FITA` diz, com todas as letras: *"a proposta da Imagem 2: **grupos nomeados**, ícone
grande com rótulo (S‑227)"*. Medi o cromo vivo:

```
  QLabel VISIVEIS dentro do cromo (cabecalho de grupo?): 0
  nomes de grupo ACESSIVEIS (invisiveis na tela):        5
      ['Arquivo', 'Edição', 'Estudo', 'OCR', 'Visualização']
```

**Os cinco grupos existem — só que apenas para o leitor de tela.** Foi o ciclo 10 que os
acrescentou (`moldura.setAccessibleName(grupo.rotulo)`), para responder às onze colisões de nome
que o `setAccessibleName` da fita expôs. O portão passou a ler o anúncio inteiro e ficou
satisfeito; o olho continua vendo **24 botões em duas filas sem uma palavra de separação**. Uma
fita sem cabeçalho de grupo não é uma fita — é uma barra de duas alturas. O Affinity rotula os
grupos da barra dele; o Chessbase 17 rotula os da fita dele.

### 2. Ritmo espacial — **NÃO SOBREVIVE, e agora o pior está na `fita`**

O item de sempre continua onde estava, medido com `c6_aberto.py` sem alteração:

```
  1920: Estudo 29 botoes em 4 filas [(12,8), (42,10), (72,4), (108,7)]
  1366: Estudo 29 botoes em 6 filas [(12,6), (42,2), (72,9), (108,1), (138,4), (168,7)]
  1280: idem                                              ^^^^^^^ uma fila com UM controle
```

E há um item **novo, que o conserto do bloqueante criou** e que nenhum dos dois lados mediu. A
geometria dos 24 botões da fita, lida do widget vivo (`c11_alinhamento_da_fita.py`, 1366×768):

```
  topos distintos:   [0, 6, 49, 55]        alturas distintas: [31, 43]
  botoes COM rotulo: 18 -> topos [0, 6, 49]
  botoes SEM rotulo:  6 -> topo  [55]  altura [31]

  ... x= 282 larg= 95 alt=43  topo=49 base=92  'Ajustar à página'
      x= 378 larg= 49 alt=31  topo=55 base=86  ''            <<< SEM ROTULO
      x= 428 larg= 49 alt=31  topo=55 base=86  ''            <<< SEM ROTULO
      x= 478 larg= 82 alt=43  topo=49 base=92  'Tirar a caixa'
```

**Na mesma fila, dois botões vizinhos diferem 12 px de altura e ficam 6 px encravados em cima e
6 px em baixo.** É visível a olho nu no recorte a 3× do próprio construtor
(`z_fita_ribbon_esq.png`): a faixa cinza que aparece acima e abaixo das duas lupas é o buraco que
os botões curtos deixam. O construtor declarou **metade** disto — *"nos dois de zoom o olho sente
a falta"* (§1.6) — como *falta de rótulo*. A outra metade é geometria, e é a carta §3.3 duas
vezes: *"espaçamento inconsistente entre elementos equivalentes"* e *"alinhamento óptico errado"*.

Casa do tabuleiro, medida no widget a 1920 (`c11_casas_do_tabuleiro.py`):

| | clássica | Foco | fita |
|---|---|---|---|
| Estudo (`TabuleiroDeJogo`) | 584/8 = **73,000 px** ✔ | **73,000** ✔ | 597/8 = **74,625** ✘ |
| Resultado (`TabuleiroEditavel`) | 697/8 = **87,125** ✘ | 665/8 = **83,125** ✘ | 649/8 = **81,125** ✘ |

O da Estudo **fechou num inteiro** — era 72,125 no ciclo 9 e é 73,000 agora nas duas peles
confortáveis. Registro a melhora. O da Resultado não fecha em nenhuma pele: uma casa sai com 88 px
e sete com 87.

### 3. Alinhamento — **o glifo morreu de verdade; a grade do ícone não fecha, e piora num eixo que ninguém mediu**

`GLIFOS DE TEXTO em TODAS as peles: 0`, reproduzido por mim com o censo do ciclo 10 e com o do
ciclo 7 sem alteração. **E eu procurei glifo fora do alcance do censo** — ele só olha
`QAbstractButton` cujo `text()` não tem letra. Varri rótulo, cabeçalho de tabela, item de tabela,
item de menu e aba, nas 3 peles × 3 densidades (`c11_glifo_em_qualquer_lugar.py`): **nenhum glifo
fazendo papel de ícone**. O produto também não usa `QStyledItemDelegate` em lugar nenhum, então o
vetor "glifo desenhado por delegado" que a ordem de serviço mandou tentar **não existe hoje**.
O conserto é real e eu não consegui furá‑lo.

A grade continua aberta, com o número do construtor: **caixa única em 10 de 12 grades**, as duas de
fora com amplitude **0×3 px** (pílula da Foco, 18 px) e **0×11 px** (fita compacta, 20 px); tinta
de **11,2 % a 48,5 %**, amplitude relativa **124,7 %**.

**E há um eixo que nenhum portão percorre.** `Ver ▸ Aparência` oferece **três peles × duas
densidades = seis arranjos**; os portões medem **três** — cada pele na densidade que ela sugere.
Rodei o censo com `CVOFF_DENSITY=confortavel`, que é o que quem escolhe "Confortável" no menu
recebe:

```
  fita, modo pleno (32 px):
     so-de-icone  6 botoes  caixas [(31,31),(31,32),(32,32)]         amplitude 1x1 px   (era 0x0)
     com texto   18 botoes  caixas [(30,32)..(32,32), (31,15), (31,24), (32,22), (32,27)]
                                                                     amplitude 2x17 px  (era 0x11)
```

**A amplitude que o relatório publica como 0×11 px é 2×17 px na outra densidade da mesma pele**, e
a caixa deixa de ser única também na família só‑de‑ícone. Nenhum glifo aparece, e o portão de
teclado continua `PASSOU` nos três arranjos não medidos (216 / 240 / 360, idênticos) — então o eixo
não esconde bloqueante. Esconde um número.

Justiça: **o portão de contraste é o único que já percorre a densidade** — `lista = [CONFORTAVEL,
COMPACTA]`, as duas folhas, e o motivo está escrito. É o modelo que os outros precisam copiar.

### 4. Densidade × vazio — **NÃO SOBREVIVE, e o 4K é onde dói**

Medido com `c5_vazios.py` do crítico do ciclo 5, sem uma linha alterada, sobre as 72 capturas.

| painel | 1920 claro | 1920 escuro | 1920 fita | **3840 claro** |
|---|---|---|---|---|
| Revisão | 394,0 | 360,5 | 326,5 | **3 104,2 kpx** |
| Texto | 425,0 | 408,2 | 394,3 | **2 050,6** |
| Dataset | 370,3 | 353,5 | 347,7 | **1 905,3** |
| Estudo | 281,5 | 268,0 | 265,4 | **1 569,6** |
| Galeria | 224,0 | 208,0 | 199,4 | **1 550,0** |
| Resultado | 118,7 | 135,6 | 73,6 | **43,3** |

**Os doze números de 1920 batem à decimal com o publicado**, e os do 4K batem em cinco de seis —
a exceção é o Dataset, e ela é o §4.1 abaixo.

**10 de 12 acima de 200 kpx a 1920; 6 de 6 a 3840.** Abri a captura inteira da Revisão a 4K: as 27
linhas da fila ocupam a faixa de cima e abaixo há **2 132×1 456 px de folha branca contínua**, sem
listra, sem rodapé de tabela, sem nada que termine a tabela. E o Texto a 4K é um painel de
2 143×2 071 px com **três linhas de estado vazio centradas no meio** (`z11_4k_texto.png`).

O Resultado **melhora com a tela** — 118,7 → 43,3 kpx, ocupação 73,1 % → 89,4 % — e isso é desenho
bom, do mesmo produto, na mesma janela. É a prova de que o problema dos outros cinco painéis é
escolha e não fatalidade.

### 5. Cor como sinal — **SOBREVIVE. Continua o melhor item da frente, e agora medido nas três peles.**

Censo de matiz meu, restrito ao cromo (painel esquerdo, sem o visor), saturação > 0,25:

| captura | cromo em cor | famílias (> 2 %) |
|---|---|---|
| claro 1920 Texto | **0,040 %** | **210° apenas** |
| escuro 1920 Texto | 0,041 % | **210° apenas** |
| **fita** 1920 Texto | 0,036 % | **210° apenas** |
| claro / escuro / fita 1920 Revisão | 0,083 / 0,084 / 0,068 % | 210° (99,4 %–100 %) |
| **fita 1366 Galeria** | 0,083 % | **210° apenas** |

**Um matiz, menos de um décimo de por cento da superfície, idêntico nas três peles.** O ciclo 9 só
conseguiu medir duas. Nível Affinity, e agora com a terceira pele dentro da conta.

### 6. Tipografia da interface — **SOBREVIVE, com uma inconsistência nova e medida**

`c9_tipografia_na_tela.py` do ciclo 9, sem alteração:

```
  858 strings desenhadas lidas em 3 peles
  aspa reta 0 · apostrofo reto 0 · "..." 0 · hifen entre espacos 0 · faixa com hifen 0
  TOTAL de ocorrencias: 0
```

Eram **864**; são **858** porque os seis glifos puros da fita deixaram de ser desenhados. O delta
explica‑se sozinho e é a favor do conserto.

**Órfãs: 0 de 18**, e eu conferi a régua nos dois sentidos — `--sem-conserto` devolve **6 de 18**,
alterando só o espaço inquebrável do texto medido. As **6 curtas (< 20 %)** que apareceram estão
declaradas, com o número.

**Régua nova, e ela é o primeiro item Visual da carta — *"qualquer texto cortado, sobreposto ou com
reticências onde caberia"*.** Oito ciclos mediram elisão em dois lugares (o rodapé e a coluna
`Motivo`). Varri **todo** widget visível com texto, comparando a largura que a fonte pede com a que
o widget dá, nas 3 peles × 3 larguras (`c11_texto_cortado.py`):

```
  classica 1280 / 1366 / 1920 : 0 · 0 · 0
  foco     1280 / 1366 / 1920 : 0 · 0 · 0
  fita     1280 / 1366 / 1920 : 0 · 0 · 0
  TOTAL de textos cortados/elididos: 0
```

**Zero em nove combinações.** É uma conquista que ninguém tinha medido e eu a registro.

A ressalva é de convenção, e é da mesma família da carta (*"traço errado"*). O produto declara o
separador dele — `" · "`, em `ui/estado_do_rodape`, `ui/strings`, `qt/painel_de_resultado`,
`qt/painel_da_galeria`, `qt/campo`, `qt/paleta` — **dez lugares**. E usa `" | "` em **quatro**:

```
  qt/painel_de_estudo.py:634   f"{texto} | vez: {turno}"        <- desenhado em toda pele
  qt/painel_de_revisao.py:297  f"{...} | {taxa:.0%} com sinal"  <- desenhado em toda pele
  ui/pedido_de_treino.py:73    " | ".join(partes)
  ui/resumo_do_dataset.py:155  " | ".join(partes)
```

Os dois primeiros estão na tela em todas as peles e larguras: `Clique em uma peça para estudar. |
vez: brancas`. Nenhuma das cinco regras do censo tipográfico olha para isso.

### 7. Controles — **SOBREVIVE. É a maior conquista do ciclo, e a conta que ela custou está publicada.**

O bloqueio do ciclo 9 era 1,88:1 na pele Foco. Remedi:

```
  classica   vivo<->morto 3.66:1   morto<->superficie 5.04:1   mortos >= vivo mais fraco: 1 de 26
  foco       vivo<->morto 3.27:1   morto<->superficie 4.10:1   mortos >= vivo mais fraco: 1 de 26
  fita       vivo<->morto 3.66:1   morto<->superficie 5.04:1   mortos >= vivo mais fraco: 1 de 26
  ESTADO MORTO em TODAS as peles: >= 3,0:1
```

**22 de 22 → 1 de 26 na pele Foco.** E o portão de contraste cobra a distância como par próprio:
**300 pares / 220 sob portão / 0 reprovados** nas duas polaridades, menor folga **3,27:1** e
**3,03:1**. O construtor publicou também o número que **piorou** por causa da escolha
(`morto ↔ superfície` de 7,14:1 para 4,10:1) e escreveu por que escolheu assim — a WCAG 1.4.3
isenta o texto de componente inativo do piso de 4,5 e não isenta ninguém de dizer que o controle
está desligado. Concordo com a escolha e com o modo de publicá‑la.

O olho confirma: em `z_fita_ribbon_1366.png`, `Cancelar a varredura` lê‑se claramente apagado ao
lado de `Varrer o livro`, `Buscar por nome` e `Buscar pela posição`. Era esse par que, a 2×, o
ciclo 9 não conseguiu separar.

### 8. Estados vazios — **SOBREVIVE na medida, e é a porta que dá no bloqueante**

`12 linhas por pele, 0 não desenhados, 0 duplicados`, nas três peles e nas quatro larguras. Nunca
dois, nunca zero. É bom desenho e é boa régua.

E é também onde o bloqueante aparece de graça: um dos três nomes que o portão certifica que estão
**desenhados** é `Achar no texto…`. O comando existe, o botão existe, o estado vazio o nomeia — e
a janela que ele abre tem **dois `QLineEdit` sem nome acessível**. O estado vazio anuncia uma porta
que dá numa sala que nenhum portão visitou.

### 9. A pele escura — **SOBREVIVE, e agora as três peles estão na conta**

**300 pares / 220 sob portão / 0 reprovados**, com as **duas densidades** varridas, menor folga
**3,03:1**. Olhando `prancha_escuro.png` inteira: o cromo escurece e **a folha do livro e o
tabuleiro ficam na paleta medida** — cromo escuro com página creme, que é o que a Imagem 1 propõe e
o que `ui/pele.FOCO` declara. Projetada, não invertida. O `pressionado` escurece; a listra é
própria.

---

## §2 — Os portões, remedidos (carta §6)

| portão | placard do construtor | minha medição | veredito |
|---|---|---|---|
| **Teclado + nome + papel, 3 peles** | 216 / 240 / 360; 0/0/0/0; PASSOU nas três | **idêntico à unidade**, e `Veredito de TODAS as peles: PASSOU` | **CONFIRMADO** |
| **…nas 3 densidades não medidas** | — | `classica/compacta`, `foco/compacta`, `fita/confortavel`: **216 / 240 / 360, 0 defeitos, PASSOU** | **ALARGADO por mim** |
| **Guarda de largura (estrutural?)** | `peles_registradas()` lê `ui/pele.PELES`; tirar a fita reprova | **testado por mutação**: quarta pele registrada → o portão a percorre; `capture.PELES` sem a fita → **FALHA**; `TAMANHOS` sem o 4K → **FALHA** | **CONFIRMADO — é estrutural** |
| **Censo de ícones, 3 peles** | 0 glifos; 12 grades, caixa única em 10; 0×3 e 0×11 | **idêntico**. E fora do alcance dele (rótulo, cabeçalho, item, menu, aba): **0 glifos** | **CONFIRMADO e alargado** |
| …na densidade não medida | — | `fita/confortavel`: grade de **32 px**, amplitude **2×17 px** e **1×1 px**; glifos **0** | **NÚMERO NOVO** |
| **Prova de vida (dois sentidos)** | 90 acusados / 6 glifos; sha confere | **90 acusados, 6 glifos**, `sha256 1f27fac6…4a` — conferido por mim antes e depois | **CONFIRMADO à unidade** |
| Contraste WCAG AA | 300 / 220 / 0; 3,27 e 3,03 | **300 / 220 / 0**; 3,27:1 e 3,03:1 | **CONFIRMADO** |
| Estado morto | 3,66 / 3,27 / 3,66 : 1; 1 de 26 | **idêntico nas três peles** | **CONFIRMADO** |
| Órfãs | 0 de 18 (6 antes) | **0 de 18**; `--sem-conserto` **6 de 18** | **CONFIRMADO nos dois sentidos** |
| Estado vazio na tela | 36 linhas, 0/0 | **12 por pele, 0 não desenhados, 0 duplicados**; `c8_vazio_na_tela.py` **30 de 30** | **CONFIRMADO** |
| Progresso | 8 indicadores, 13 operações, 0 invisíveis | **idêntico**, `Nenhum defeito bloqueante de progresso` | **CONFIRMADO** |
| **`determinado` por operação** | 0/0 · 0/0 · **4 bloqueantes, 4 divergências** | **idêntico**; `sha256 8f45d98e…26` confere | **CONFIRMADO** |
| …sob um tique **maior** que `ASSENTAR_MS` | — | `singleShot(250)` → **4 bloqueantes, 4 divergências**. O portão erra para o lado que **acusa** | **NÃO É FURO** |
| **Execução (tronco vivo)** | 5 aberturas / 9 ações, 0 sem cobertura, 0 não atribuídas | **idêntico à unidade**, `PASSOU` | **CONFIRMADO** |
| Execução, sabotagens | `sab_c9` não executável; `sab_c9x` 8/8+4/4; `sab_c10` 8/8+5/5 | **idêntico**, e confirmo que `QtConcurrent` não existe neste PyQt6 | **CONFIRMADO** |
| …contra a **fronteira de mecanismo** | *"para atravessá‑la é preciso sair do Python"* | `sab_c11`: **1 de 4**. `_thread.start_new_thread`, `multiprocessing.Process` e `ctypes/CreateThread` **escapam** — e as três são biblioteca‑padrão | **A AFIRMAÇÃO ESTÁ LARGA — §5.4** |
| Vazio de painel, 1920 | 425,0 / 394,0 / 370,3 / 281,5 / 224,0 / 118,7 | **idêntico à decimal**, claro e escuro; fita com **1** painel abaixo de 200 kpx (Galeria 199,4) | **CONFIRMADO** |
| Vazio de painel, 4K | Revisão 3 104,2 · Texto 2 050,6 · Dataset **1 912,4 †** · Estudo 1 569,6 · Galeria 1 550,0 · Resultado 43,3 | **cinco batem à decimal; o Dataset me devolve 1 905,3** (painel 2143×2071, maior vazio 2136×892 em (14,1135)) | **CONFIRMADO menos um — §4.1** |
| Tipografia da tela | — | **858 strings, 0 faltas** nas 5 regras (eram 864 com os 6 glifos) | **CONFIRMADO e explicado** |
| **Texto cortado (régua nova)** | — | **0** em 3 peles × 3 larguras, todo widget com texto | **NOVO, e a favor** |
| A janela sem torch | 7 de 7 / 4 de 4 | **7 de 7** e **4 de 4**, `Veredito: PASSOU` | **CONFIRMADO** |
| **Suíte do tronco** | 4 failed, 4 485 passed, 2 skipped, 4 536 subtests | **4 failed, 4 485 passed, 2 skipped, 4 536 subtests** em **318,05 s**; `diff` das listas de `FAILED`: **idêntico** | **CONFIRMADO campo a campo** |
| **Suíte nossa, sem `test_packaging.py`** | 3 049 passed, 1 skipped, 0 failed (duas vezes) | **3 049 passed, 1 skipped, 0 failed** em 746,02 s — e o **mesmo** pulo (`test_fonts.py:333`, Brotli) | **CONFIRMADO numa terceira execução** |
| `tests/unit/ui` | 161 passed | **161 passed** em 1,75 s | **CONFIRMADO** |
| `test_field_eval.py` | 1 reprovação, 4 relatórios, 3 módulos | **1 failed, 100 passed, 142 subtests**; os 4 relatórios e os 3 módulos, nomeados | **CONFIRMADO — §4.2** |

**O portão de bloqueio eu remedi depois de as suítes acabarem, com a máquina livre**, três
execuções como a carta manda:

```
  abrir PDF (load_pdf, 1a pagina a 300 DPI):  207 · 212 · 205 ms  -> mediana 207 ms
  7 operacoes acima do piso de 16 ms          -> Veredito: REPROVOU  (nas tres)
  DESTA FRENTE (qt/ + ui/):  4.2 / 3.9 / 3.4 ms  = 1.5 % / 1.9 % / 1.7 % do perfilado
  COBERTURA do perfil: 139.1 % / 97.2 % / 99.7 %
```

**REPROVA, e a parte desta frente é 1,5 %–1,9 %** — exatamente como o relatório declara. A minha
mediana é menor que os 272 ms dele porque a máquina dele estava disputada; a reprovação é a mesma.
A pilha do pior nomeia `fz_run_display_list` (66–87 ms, `painel_do_pdf.py:802`), `nt.stat`
(29–41 ms, `marcas.py:77 _marca_de`) e **`sqlite3.Connection.execute` a 37–38 ms em
`janela.py:1763 _atualizar_abas`** — este último é um caminho de E/S de disco na thread da janela
que **não está nomeado em nenhum dos dois documentos**; o ciclo 9 nomeou `estudo_arquivo.py:85`,
`marcas.py:77` e `painel_da_galeria.py:1087`.

O portão de quadros eu **não** remedi: as três execuções de fps que eu poderia rodar ficariam
sobre uma máquina que acabou de correr quatro suítes, e é a armadilha que o construtor já
documentou publicando as duas medições lado a lado. O número dele (zoom **64,0 fps @ p95** ociosa,
reprovando duas vezes com as suítes ao lado) fica de pé como estava.

---

## §3 — Defeito bloqueante

### 1. O portão de nome e papel percorre as três peles e as seis abas — e nunca abriu um dos doze diálogos do produto. Onze controles chegam ao leitor de tela sem nome.

**Onde.**
Portão: `src/caissa/ui/audit/teclado.py::auditar` — percorre `janela.abas`, e só.
Produto: `chess_diagram_ocr/qt/dialogos.py` (5 diálogos), `qt/legenda.py`, `qt/paleta.py`,
`qt/painel_de_texto.py:1377`, `qt/painel_do_dataset.py:105`, `qt/painel_de_estudo.py:1849/1881/1917`.
Causa: `qt/janela.py:361` — a **única** chamada de `acessibilidade.nomear_tudo` em todo o produto.

**O que.** O produto tem **doze `QDialog`**:

```
  dialogos.py:98  DialogoDeBases        dialogos.py:280 DialogoDeEscopo
  dialogos.py:409 DialogoDePartidas     dialogos.py:641 DialogoDeTreino
  dialogos.py:680 ControladorDeTreino   legenda.py:51   JanelaDeAtalhos
  paleta.py:97    JanelaDaPaleta        painel_de_texto.py:1377   JanelaDeBusca
  painel_do_dataset.py:105 JanelaDeEstatisticas
  painel_de_estudo.py:1849/1881/1917  _JanelaDeColar / _JanelaDeColecao / _JanelaDePartidas
```

e três dos arquivos que os montam não têm **uma** chamada de `setAccessibleName`:

```
  qt/dialogos.py    setAccessibleName x0   setBuddy x0
  qt/legenda.py     setAccessibleName x0   setBuddy x0
  qt/paleta.py      setAccessibleName x0   setBuddy x0
  --- para comparar, na janela principal ---
  qt/painel_do_pdf.py x4   qt/painel_de_texto.py x8   qt/painel_de_resultado.py x7
```

`JanelaDeBusca` monta `QLabel("Achar", self)` ao lado de `QLineEdit(self)` e
`QLabel("Trocar por", …)` ao lado de `campo_novo` — **sem `setBuddy` e sem
`setAccessibleName`**. Um `QLabel` vizinho num leiaute não dá nome a um campo no Qt; só o *buddy*
dá. `setBuddy` aparece **3 vezes em todo o produto**, e nenhuma delas num diálogo.

Aplicando a régua do próprio portão (`teclado.Controle`, `_focaveis`, `_nome_de`, `_papel_de`,
`_grupo_de`, `Aba.anonimos()/sem_papel()`), sem alterar uma linha:

```
  JanelaDaPaleta       (Ctrl+Shift+P)   2 focáveis   SEM NOME: QLineEdit, TabelaQt
  JanelaDeBusca        (Achar…)         5 focáveis   SEM NOME: QLineEdit, QListWidget
  JanelaDeBusca        (substituindo)   7 focáveis   SEM NOME: QLineEdit, QLineEdit, QListWidget
  JanelaDeAtalhos      (Ver ▸ Atalhos)  2 focáveis   SEM NOME + SEM PAPEL: QScrollArea
  JanelaDeEstatisticas (Dataset)        1 focável    SEM NOME: QPlainTextEdit
  _JanelaDeColar       (Estudo ▸ Colar) 3 focáveis   SEM NOME: QTextEdit
  ------------------------------------------------------------------------
  11 defeitos.  Na janela principal, a mesma regua: 11 QLineEdit + 1 QTextBrowser
                + 3 QTextEdit  ->  0 sem nome.
```

*(Uma ressalva de honestidade: a régua também acusa `QPushButton 'OK'` em `_JanelaDeColar` por
`sem letras`, porque `LETRAS_MINIMAS = 3` e "OK" tem duas. Isso é **artefato da régua**, não
defeito do produto, e eu o tiro da conta. Os 11 acima são todos `anonimos()`/`sem_papel()`.)*

**Como reproduzir.**

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONPATH=<suite>\src;<tronco>\src
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe ^
    benchmarks\reports\critique\ui\c11\c11_dialogos.py classica
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe ^
    benchmarks\reports\critique\ui\c11\c11_dialogos_prova.py
```

Ou, sem rodar nada: abra o programa, aperte **`Ctrl+Shift+P`** e leia `qt/paleta.py` — não há
`setAccessibleName` no arquivo, e o campo de busca da paleta é `QLineEdit` cru.

**Por que reprova.**

1. **É o décimo instrumento cego desta frente, e é o segundo cego por *escopo*.** O ciclo 9
   reprovou porque o portão media **uma pele de três** e publicava `PASSOU` sem dizer qual. O
   ciclo 10 consertou a largura no eixo *pele* — e o consertou bem, estruturalmente, como eu
   verifiquei por mutação. Mas o portão publica `0 sem nome` sobre **a janela principal**, sem
   dizer que é a janela principal, e o mesmo comando, aplicado ao diálogo ao lado, devolve
   **11 defeitos**. A carta §6 manda remedir o número do construtor; remedido fora do escopo em que
   ele foi medido, ele inverte — que é literalmente o §3 do ciclo 9 outra vez, num eixo diferente.

2. **É o defeito nº 1 do ciclo 1 desta frente, e é pior que o daquele ciclo.** O ciclo 1 mediu 28
   controles que chegavam ao leitor de tela como `-`, `+`, `|◀`, `.md`. Um glifo pelo menos
   anuncia *alguma coisa*. Estes **não têm nome nenhum**: o Qt anuncia "caixa de edição" e nada
   mais. Em `Achar e substituir` são dois campos de edição consecutivos, indistinguíveis.

3. **A superfície mais atingida é a que existe para quem usa o teclado.** `JanelaDaPaleta` é a
   paleta de comandos, o décimo quarto atalho de `ui/atalhos.py:222`
   (`Atalho("<Control-P>", "Ctrl+Shift+P", "paleta_de_comandos", …)`). Uma paleta de comandos é,
   por definição, a superfície de quem não usa o mouse — e o campo onde se digita não tem nome.

4. **O produto já tem o conserto, com a decisão tomada e escrita, e ele nunca correu ali.**
   `qt/acessibilidade.py` existe exatamente para isto, e o docstring dele antecipa este defeito:
   *"as vinte chamadas seriam vinte lugares que alguém precisa lembrar, e a vigésima primeira — o
   campo que o próximo item acrescenta — nasceria muda"*. A varredura roda **uma vez**, em
   `qt/janela.py:361`, dentro do `__init__` da janela principal; **todo diálogo nasce depois**.
   Chamei‑a à mão em cada um dos seis:

   ```
     DEFEITOS nos 6 dialogos:  antes = 11   depois de nomear_tudo = 0
        JanelaDeBusca:  QLineEdit -> 'Achar'   QLineEdit -> 'Trocar por'   QListWidget -> 'Lista'
        JanelaDaPaleta: QLineEdit -> 'Campo de texto'   TabelaQt -> 'Tabela de resultados'
        JanelaDeAtalhos:QScrollArea -> 'Atalhos de teclado'
        _JanelaDeColar: QTextEdit -> 'Cole aqui uma FEN ou um PGN. …'
   ```

   Onze viram zero, e os nomes derivados são os certos. Não é um item de desenho: é uma linha que
   não foi chamada num lugar que ninguém mediu.

5. **Nenhum ciclo o declarou fora de escopo.** Varri os onze documentos desta frente: os diálogos
   aparecem **três vezes**, todas sobre a barra de progresso do `DialogoDeTreino` (C3 §10, C4, o
   inventário de progresso). O portão de nome e papel nunca os mencionou, nem para excluí‑los.

**O conserto é uma chamada de produto e um `for` no arnês** — a mesma forma do conserto do ciclo 9:

* **Produto**: a varredura passa a alcançar todo diálogo. O desenho que o próprio módulo defende é
  **uma** varredura e não doze chamadas: um filtro de evento de aplicação em `QEvent.Show` para
  `QDialog`, ou um `showEvent` numa base comum. Doze `nomear_tudo(self)` espalhados são exatamente
  o antipadrão que `qt/acessibilidade.py` recusa por escrito.
* **Arnês**: `caissa.ui.audit.teclado` percorre também os diálogos, e a lista sai **do produto** —
  do mesmo jeito que `peles_registradas()` lê `ui/pele.PELES`. O produto já tem meia lista em
  `qt/__init__._POR_MODULO` (`JanelaDaPaleta`, `JanelaDeAtalhos`, `JanelaDeBusca`,
  `DialogoDeBases`, `DialogoDeEscopo`, `DialogoDePartidas`, `ControladorDeTreino`); os cinco que
  faltam precisam de uma declaração, e é ela que o portão deve ler.

*Alvo, cobrado por teste: o portão de teclado publica **uma linha por diálogo registrado** e
devolve `0 sem nome, 0 sem papel, 0 nome vazio` em cada um, nas três peles. Prova de vida: tirar a
varredura de um diálogo faz o portão reprovar naquele diálogo — hoje ele passa porque não olha. E
um teste do tipo de `TestTodasAsPeles` compara a lista de diálogos do arnês com a do produto e cai
quando o décimo terceiro entrar.*

---

## §4 — Os dois julgamentos que a ordem de serviço pediu

### 4.1 Publicar os dois números do Dataset a 4K: **honesto no espírito, errado na ordem**

Medi com `c5_vazios.py` sem alteração, sobre as mesmas capturas: **1 905,3 kpx** (painel 2143×2071,
maior vazio 2136×892 em (14,1135)). As outras cinco linhas da coluna de 3840 batem à decimal
(3 104,2 · 2 050,6 · 1 569,6 · 1 550,0 · 43,3). **O 1 912,4 não reproduz; o 1 905,3 reproduz.**

O que o construtor fez está certo em duas coisas e errado em uma:

* **Certo**: não escolheu em silêncio. Um agente que mede 1 905,3 e publica 1 912,4 porque é o que
  já estava escrito comete o defeito que esta frente passou onze ciclos a caçar. Publicar a
  divergência, com o painel e as coordenadas, é o comportamento que a carta pede.
* **Certo**: disse que a conclusão do item não depende de qual vale — e não depende mesmo. Os seis
  painéis passam de 200 kpx a 4K nos dois casos, e o pior é a Revisão nos dois.
* **Errado**: deixou o número **irreprodutível na tabela** e o reprodutível na nota de rodapé. A
  carta §6 é explícita — *"se você não conseguir reproduzir a medição, o veredito é REPROVADO com
  a justificativa 'métrica não reproduzível'"*. Aqui não reprova, porque é uma célula de um item
  aberto e o número certo está no mesmo documento; mas a tabela deve trazer o que a régua devolve
  hoje, e a história vai para a nota. Inverter isso é fazer o leitor apressado citar o número que
  ninguém consegue obter.

**Veredito: escrituração honesta com a ordem trocada.** Não bloqueia. Entra no §7 como correção de
uma linha.

### 4.2 Recusar o conserto de `test_field_eval` por proveniência: **a decisão certa, e ela ainda não está fechada**

Reproduzi a reprovação: `1 failed, 100 passed, 142 subtests`, os quatro relatórios
(`controle_20260822`, `field_20260822_s99`, `mhsp_20260822`, `s108_20260822`) e os três módulos
(`checkpoint`, `inference`, `service`), exatamente como o relatório diz. E li a guarda: ela compara
o digest do fecho de imports do caminho de medição e **é desenhada para disparar em qualquer
mudança de código**, dizendo no próprio docstring que não é papel dela saber se a mudança é inerte.

**A favor do construtor, e é muito:**

1. **Não tocou no teste.** Nada de `skip`, `xfail`, lista de exceção ou tolerância. É a linha que
   mais importa, e ela foi respeitada.
2. **Pagou a recusa com um número**, obtido pela ferramenta que o próprio teste nomeia
   (`cvoff-field --json`), gravando num arquivo temporário: **1 080 métricas comparadas, 0
   diferentes**; as únicas 64 diferenças em 1 150 campos são `seconds` e `seconds_per_diagram`.
   Isso não é uma justificativa, é uma medição — e é o que a carta §6 pede de qualquer afirmação.
3. **O argumento de proveniência não é retórica.** Remedir reescreveria quatro arquivos de
   `docs/metrics/` que outros documentos citam como correntes, com a assinatura de outra frente, e
   gravaria `dirty: true` sobre um `dirty: false` publicado num commit limpo. Uma frente que
   reescrevesse dado de medição alheio para deixar a própria suíte verde estaria a fazer algo pior
   do que deixar um teste vermelho com um número ao lado.
4. **Publicou a reprovação em três lugares** do relatório, incluindo a tabela de suítes, e disse
   "a quarta é minha".

**Contra, e é o que impede de chamar isto de fechado:**

1. **A suíte do tronco ficou mais vermelha do que estava** — 3 → 4 —, e "o dono é outra frente" é
   uma entrega, não um fecho. A carta §5.2 recusa a justificativa; ela não distingue "limitação da
   biblioteca" de "arquivo de outro dono".
2. **Existe um terceiro caminho, e o próprio construtor o nomeou**: remedir numa árvore limpa, para
   o `dirty` sair certo. Ele escreveu *"de preferência numa árvore limpa"* e não o fez. Isso é
   escopo, não impossibilidade — e escopo é uma escolha que se justifica por uma vez, não por duas.

**Veredito: recusa correta, prova correta, item ainda aberto.** Não bloqueia F9 — o defeito não
está na interface e a medição prova que nada de qualidade se moveu. Mas entra no §7 com dono,
método e prazo: **não pode sobreviver a mais um ciclo**.

### 4.3 A evidência de suíte, verificada

Rodei a do tronco: **4 failed, 4 485 passed, 2 skipped, 4 536 subtests em 318,05 s**, e o `diff` da
lista de `FAILED` contra a do relatório é **idêntico** — as três de sempre mais o
`test_field_eval` do item 9. Bate campo a campo.

Rodei a nossa **sem `tests/integration/test_packaging.py`**, que é a linha com que o relatório
responde à pergunta de determinismo desta frente: **3 049 passed, 1 skipped, 0 failed** em
746,02 s, com o **mesmo** pulo de sempre (`test_fonts.py:333`, WOFF2 sem o compressor Brotli).
É a **terceira** execução independente a devolver esse número — as duas do construtor e a minha,
numa árvore em que outro agente reescreveu o `dist/` no meio. **O que esta frente escreve não
varia**, e agora isso está medido três vezes por dois agentes.

A atribuição da deriva de 4 testes na suíte inteira **também confere no mecanismo**:
`tests/integration/test_packaging.py` pula quando `dist/Caissa` ou `packaging/bundle-com-torch.json`
não existem (`test_packaging.py:601`, o pulo que o relatório nomeia), e o `dist/` desta árvore foi
reescrito por outro agente — `dist/Caissa` às 19:29 e `dist/caissa-0.1.0-padrao-proxy.7z` às
19:31, **depois** das execuções do relatório. Um arquivo de teste cujo número de casos coletados
depende do artefato que outro agente reescreve é a explicação certa, e ela é verificável sem
confiar no carimbo.

---

## §5 — Defeitos não bloqueantes

Em ordem de custo, com a medida de cada um.

### 5.1 A `fita` promete "grupos nomeados" e desenha zero

`ui/pele.FITA`, o próprio produto: *"a proposta da Imagem 2: **grupos nomeados**, ícone grande com
rótulo"*. Medido no cromo vivo: **0 `QLabel` visíveis dentro da fita**, **5 nomes de grupo
acessíveis** (`Arquivo`, `Edição`, `Estudo`, `OCR`, `Visualização`). Os cinco nasceram neste ciclo,
para o portão. *Alvo: o cabeçalho de grupo é desenhado — o mesmo texto que o `accessibleName` já
carrega. Hoje 0 de 5.*

### 5.2 O conserto do bloqueante deixou seis botões 12 px mais curtos e 6 px encravados

Medido no widget (`c11_alinhamento_da_fita.py`): 4 topos distintos (0, 6, 49, 55) e 2 alturas
(43, 31) em duas filas; os 6 sem rótulo são `topo=55 alt=31` entre vizinhos `topo=49 alt=43`.
Visível em `z_fita_ribbon_esq.png` como faixa cinza acima e abaixo das duas lupas. O construtor
declarou a falta de rótulo; a geometria não. *Alvo: numa fila da fita, um topo e uma altura.*

### 5.3 A grade do ícone é 0×11 px numa densidade e **2×17 px** na outra

Medido com o censo do construtor sob `CVOFF_DENSITY=confortavel`: a fita passa para a grade de
32 px e a família "com texto" sai com caixas de (30,32) a (32,32) mais (31,15), (31,24), (32,22),
(32,27) — **amplitude 2×17 px** —, e a família só‑de‑ícone deixa de ser única (**1×1 px**). A causa
é a declarada: `ui/icones.na_grade` enche o lado maior. *Alvo: a caixa é única em 12 de 12 grades,
nas seis combinações de pele × densidade.*

### 5.4 O portão de execução: a fronteira declarada é mais larga do que o produto dela

O relatório declara: *"o que ele ainda não vê é trabalho aberto por biblioteca nativa que não passe
por nenhum dos oito pontos e não crie thread de Python… para atravessá‑la é preciso sair do
Python"*. Plantei quatro formas (`sab_c11/`), **três delas biblioteca‑padrão pura**:

```
  a  _thread.start_new_thread(...)          calada  <<< thread real, sem threading.Thread
  b  multiprocessing.Process().start()      calada  <<< processo de fundo real
  c  ProcessPoolExecutor().submit(...)      PEGA    (pela thread alimentadora interna dele)
  d  ctypes -> kernel32.CreateThread        calada  <<< thread nativa
  controles negativos n1..n3                calados (3 de 3)
  formas pegas: 1 de 4
```

`_thread.start_new_thread` **não sai do Python** — é uma linha da biblioteca‑padrão, e
`threading.enumerate()` não lista a thread que ela cria enquanto essa thread não tocar no módulo
`threading`. **Nenhuma das três existe no tronco hoje** (conferido), e as 16 formas curadas do
construtor são pegas 16 de 16, então isto não é uma reprovação do produto — é a afirmação de
fronteira que precisa encolher para o que ela realmente cobre. *Alvo: `threading.Thread.start`
deixa de ser o único ponto de thread; `_thread.start_new_thread` e `multiprocessing.Process.start`
entram na lista de interceptação, e a frase da fronteira passa a dizer "não passe por nenhum dos
dez pontos e não crie objeto `threading.Thread`".*

### 5.5 A certidão de higiene do ciclo 10 confere o arquivo errado — e um portão ainda reescreve a sessão de quem o roda

O relatório certifica: *"o `data/app_tkinter_state.json` do tronco continua com `mtime` 13:25…
Os portões usam `capture.estado_de_medicao(pasta)`, e ele segura"*. **É verdade, e é o arquivo do
Tk.** O estado da janela **Qt** é outro: `qt/janela.py:178` declara
`CAMINHO_DO_ESTADO = PROJECT_ROOT / "data" / "janela.json"`, e é ele que guarda `last_pdf`,
`last_page`, `pdf_zoom`, `pdf_enquadramento`, `board_zoom` e `pdf_history`.

Contei quem redireciona:

```
  teclado.py    JanelaPrincipal( x1   caminho_do_estado x1   ok
  execucao.py   JanelaPrincipal( x1   caminho_do_estado x1   ok
  capture.py    JanelaPrincipal( x1   caminho_do_estado x2   ok
  bloqueio.py   JanelaPrincipal( x2   caminho_do_estado x0   <<< le e reescreve data/janela.json
  (os cinco instrumentos c10_* redirecionam; conferido um a um)
```

`caissa/ui/audit/bloqueio.py:780` e `:798` constroem `JanelaPrincipal()` **sem argumento**. Depois
das minhas três execuções, `data/janela.json` estava com `last_pdf = 1937 Kemeri.pdf`,
`last_page = 120` e o zoom da corrida — a sessão do portão escrita por cima da de quem o rodou.

**Envenenei e medi, para saber se o número depende disso** (`pdf_zoom` 0,3055 → 1,0,
`enquadramento_pagina` → largura, página 120 → 0, `board_zoom` 0,85 → 1,6), com cópia e SHA‑256:

```
  estado herdado:     abrir PDF  207 · 212 · 205 ms
  estado envenenado:  abrir PDF  204 ms
```

**O número não depende do estado**, e isso é a favor do portão — a página é reenquadrada na
abertura. O defeito é de higiene, não de medição: o portão estraga a sessão de quem o roda, e a
certidão do ciclo 10 não o pegou porque conferiu o arquivo do Tk. Restaurei `data/janela.json` da
minha cópia (`sha256 77d24622…cd`, campo a campo idêntico) — **e digo o que não consigo desfazer**:
a cópia é do momento em que eu vi o problema, não de antes da minha primeira execução do
`bloqueio`, porque nenhum documento diz que este portão escreve ali. *Alvo: `bloqueio.py` passa
`caminho_do_estado=capture.estado_de_medicao(...)` nas duas construções, e a certidão de higiene
passa a nomear `data/janela.json`, que é o arquivo que a janela Qt usa.*

### 5.6 O separador da interface tem duas grafias

**10 lugares usam `" · "`, 4 usam `" | "`**, e dois dos quatro estão desenhados na tela em todas as
peles e larguras (`qt/painel_de_estudo.py:634` e `qt/painel_de_revisao.py:297`). Nenhuma das cinco
regras do censo tipográfico olha para isso. *Alvo: uma grafia; e a sexta regra do censo passa a
cobrá‑la — hoje 858 de 858 strings passam e quatro delas não deviam.*

### 5.7 A marca da FEN continua só do lado direito, e não está na lista de abertos do relatório

Item 7 do §6 do ciclo 9. `qt/rotulo.py:229` calcula `faixa = area.adjusted(area.width() -
self._margem, 0, 0, 0)` e `:237` desenha `RETICENCIA` nela — **há um só `drawText` e uma só faixa,
e ela é sempre a da direita**. Com o cursor no fim, o texto escondido está à esquerda e a marca
está à direita. `qt/rotulo.py` não foi tocado neste ciclo (mtime 11:03, contra 14:19 de
`qt/fita.py`), e **não aparece na tabela "o que continua aberto"** do relatório. Não é
convenientemente aberto: é um item que saiu da lista. *Alvo: a marca vai para o lado em que há
texto fora — os dois lados, quando os dois estão.*

### 5.8 `Motivo` ilegível a 1920, e também fora da lista de abertos

Item 9 do §6 do ciclo 9, reproduzido com o instrumento do construtor sem alteração: **17 de 27** a
1920, **24 de 27** a 1366, **25 de 27** a 1280. O relatório menciona o item só para dizer que o 4K
o resolve sozinho — e resolve, eu confirmo olhando `c10_claro_3840x2160_revisao.png`. Mas a 1920,
que é onde ele foi medido, ele continua igual e **não está na tabela de abertos**. *Alvo: 0 de 27
pedindo mais largura nas três larguras; há 394,0 kpx de tabela vazia logo abaixo.*

### 5.9 O paginador da Galeria: uma linguagem de seta, ±20 % de tinta

Item 8 do §6 do ciclo 9, metade fechada. O censo passou a incluir os botões com ícone **e** texto
(era o pedido) — mas a amplitude de tinta continua **124,7 %** contra o alvo de ±20 %, e o
instrumento do ciclo 9 rodado pelo construtor ainda devolve `45..87 px², 1,9×` entre irmãos do
mesmo grupo.

### 5.10 Os que continuam abertos e declarados, e eu confirmo o número

* **Bloqueio > 16 ms**: REPROVA, 7 operações. Mediana das minhas três, com a máquina livre:
  **207 ms**; a dele, com a máquina disputada, 272 ms. Declarado sem atenuar, com a E/S de disco na
  thread da janela nomeada — **e falta nomear uma**: `sqlite3.Connection.execute` a 37–38 ms dentro
  de `janela.py:1763 _atualizar_abas`, que não aparece em nenhum dos dois documentos.
* **Vazio de painel**: 10 de 12 acima de 200 kpx a 1920; **6 de 6 a 4K**, pior 3 104,2 kpx. Confirmo
  os doze de 1920 à decimal e cinco dos seis de 4K.
* **Poço à direita da paleta**: 114,5 kpx a 0,00 % de tinta.
* **Piso da janela** 1066×735: a 1024×768 a janela transborda 42 px, dito com a frase inteira.
* **Tinta dos ícones** 11,2 %–48,5 %, agora medida em quatro grades em vez de uma.
* **Última linha curta**: 6 de 18, que é o preço declarado de fechar as 6 órfãs.
* **Rótulo morto ≥ vivo mais fraco**: 1 de 26 em cada pele, e o construtor explicou que 0 de 23 →
  1 de 26 é comparação entre duas réguas, não piora.
* **Falso positivo da contagem** (`nome = self.nome_do_livro()`): declarado, com o motivo de ter
  escolhido errar para o lado que reprova.
* **2 pares com estados divergentes** na pele Foco.
* **Barra determinada no dataset**: precisa de callback fora do que esta frente escreve.

**Nenhum destes é "convenientemente aberto".** Em todos, o número publicado é o que eu meço, e em
dois deles (o poço que piorou de 109,7 para 114,5, e a `morto ↔ superfície` que caiu de 7,14:1 para
4,10:1) o construtor escolheu publicar o lado que o desfavorece. Os que **eu** classifico como
saídos da lista sem aviso são os §5.7 e §5.8 — e mesmo esses estão medidos noutro lugar do
documento, não escondidos.

### 5.11 Miudezas medidas

* Casa do `TabuleiroEditavel`: **87,125 / 83,125 / 81,125 px** nas três peles — uma casa de 88 px e
  sete de 87 no mesmo tabuleiro. O da Estudo **fechou** em 73,000 na clássica e na Foco (era
  72,125); na fita é 74,625.
* `caissa.ui.audit.execucao` tem `--saida` com padrão em `benchmarks\reports\ui\` — a pasta do
  construtor. É uma armadilha para o próximo crítico, e ela me pegou uma vez.
* O cabeçalho do portão de contraste diz *"nas duas peles"* quando o que ele percorre são **duas
  polaridades de cromo × duas densidades**. O texto está errado; a medição está certa.
* A tabela da Revisão a 4K termina numa folha branca contínua de 2 132×1 456 px, sem listra e sem
  rodapé de tabela que a encerre.

---

## §6 — O que este ciclo conquistou, e eu confirmo com número

Não estou a dar crédito por esforço. Registro o que remedi e bateu.

1. **O bloqueante está morto nas três metades, e eu ataquei as três.** O glifo saiu (0 em todas as
   peles, e 0 também fora do alcance do censo — rótulo, cabeçalho, item de tabela, item de menu,
   aba); o nome acessível entrou; e os portões percorrem `ui/pele.PELES`.

2. **A guarda de largura é estrutural, e eu a provei por mutação.** Registrei uma quarta pele em
   `ui/pele.PELES`: `teclado.peles_registradas()` passou a devolvê‑la sem que eu tocasse no arnês,
   e `test_a_captura_cobre_toda_pele_registrada` passou a **falhar**. Tirei a `fita` de
   `capture.PELES`: falha. Tirei o 4K de `TAMANHOS`: falha. **Uma pele não consegue entrar no menu
   sem entrar no portão** — e essa era a pergunta exata da ordem de serviço.

3. **A prova de vida fecha nos dois sentidos, e o furo que ela achou era do próprio portão.** Sem
   `setAccessibleName`, a cascata caía no `text()` e `"Abrir\nPDF"` passava por nome válido; o
   motivo novo `quebra de linha no nome` fecha isso, e a sabotagem devolve **90 acusados**. Com o
   glifo de volta, o censo devolve **6**. `sha256` conferido por mim antes e depois.

4. **O estado morto passou de 1,88:1 para 3,27:1 na pele Foco**, com a conta que custou publicada
   ao lado e a escolha justificada pela WCAG. **22 de 22 → 1 de 26.** O olho confirma.

5. **`determinado` deixou de ser consulta de duas entradas.** A sabotagem "nunca troca de modo"
   acusa **4 operações**; o tique de 40 ms não engana mais; e um tique de **250 ms**, maior que
   `ASSENTAR_MS`, faz o portão **acusar** em vez de calar — a régua erra para o lado seguro.

6. **A régua de threads trocou de forma e a troca é certa.** 8/8 do crítico do ciclo 9 (na
   transcrição executável) e 8/8 das do construtor, com 9 controles negativos calados; e o portão
   diz **`NAO ATRIBUIDA`** em vez de calar diante do que não conhece, que é a diferença inteira em
   relação à AST. Confirmo também que a cópia fiel do `sab_c9` **não roda neste venv** —
   `QtConcurrent` não existe no PyQt6 — e que publicar isso em vez de fingir que mediu é o
   comportamento certo.

7. **A régua gêmea no tronco achou um defeito no portão do arnês**, e o relatório conta a história
   inteira: `QThread.start` restaurado com o objeto errado, 3 reprovações → 26, e a abertura da
   página 121 que morria em silêncio (4 aberturas → **5**). Confirmo as 5 aberturas.

8. **Zero texto cortado em nove combinações de pele × largura**, com uma régua que ninguém tinha
   escrito. O primeiro item Visual da carta está limpo no produto inteiro.

9. **Zero faltas tipográficas em 858 strings desenhadas**, e o delta 864 → 858 é exatamente os seis
   glifos que saíram.

10. **Nada foi afrouxado.** A suíte do tronco fecha campo a campo (4 failed, 4 485 passed, 2
    skipped, 4 536 subtests), a nossa sem `test_packaging.py` devolve **3 049 passed, 1 skipped, 0
    failed** pela terceira vez independente e com o mesmo pulo, `tests/unit/ui` passa 161 de 161, e
    nenhum teste foi tocado — a única reprovação nova está declarada com o número que prova que
    nada de qualidade se moveu.

11. **A disciplina de caminho de saída foi respeitada pelo construtor** — os dois instrumentos meus
    do ciclo 9 que gravam no próprio diretório foram rodados de cópia em pasta temporária, com
    SHA‑256 conferido, e os `mtime` das capturas do c9 continuam os de antes. Conferi.

---

## §7 — O que especificamente precisa mudar para eu aprovar

**Um item bloqueia. Só ele.**

1. **Faça a varredura de nome acessível alcançar todo diálogo, e faça o portão de teclado abrir os
   diálogos que o produto registra.** Duas metades, as duas obrigatórias:
   - **Produto**: `qt/acessibilidade.nomear_tudo` roda em todo `QDialog` — **uma** vez, num filtro
     de evento de aplicação em `QEvent.Show` ou num `showEvent` de base comum, e não doze chamadas
     espalhadas (é o antipadrão que o próprio módulo recusa por escrito). Hoje a única chamada em
     todo o produto é `qt/janela.py:361`, sobre a janela principal, dentro do `__init__` — e todo
     diálogo nasce depois.
   - **Arnês**: `caissa.ui.audit.teclado` publica **uma linha por diálogo**, e a lista sai do
     produto, como `peles_registradas()` lê `ui/pele.PELES`. Meia lista já existe em
     `qt/__init__._POR_MODULO`; os cinco que faltam (`DialogoDeTreino`, `JanelaDeEstatisticas`,
     `_JanelaDeColar`, `_JanelaDeColecao`, `_JanelaDePartidas`) precisam de declaração.

   *Alvo, cobrado por teste: `0 sem nome, 0 sem papel, 0 nome vazio` em cada diálogo registrado, nas
   três peles. Hoje: **11 defeitos em 6 diálogos**, sendo 2 no campo da paleta de comandos
   (`Ctrl+Shift+P`) e 3 em `Achar e substituir`. Prova de vida: tirar a varredura de um diálogo faz
   o portão reprovar naquele diálogo; e um teste compara a lista do arnês com a do produto e cai
   quando o décimo terceiro entrar.*

**Não bloqueiam, e entram no §9 da próxima ordem de serviço nesta ordem:**

2. **A `fita` desenha os cabeçalhos de grupo que ela mesma promete.** *Alvo: 5 de 5 visíveis — hoje
   0 visíveis e 5 só no leitor de tela.* (`ui/pele.FITA`: *"grupos nomeados"*.)
3. **Uma fila da fita, um topo e uma altura.** *Alvo: 1 topo e 1 altura por fila — hoje 4 topos
   (0, 6, 49, 55) e 2 alturas (43, 31), com 6 botões 12 px mais curtos e 6 px encravados entre
   vizinhos de 43 px.*
4. **Os portões percorrem o eixo densidade como o de contraste já percorre.** *Alvo: 6 arranjos
   medidos (3 peles × 2 densidades) em `teclado`, `capture` e no censo de ícones — hoje 3. O número
   que isso descobre já existe: a amplitude da caixa do ícone é **2×17 px** em `fita/confortavel`
   contra os 0×11 px publicados.*
5. **Corrija a linha do Dataset a 4K**: a tabela traz **1 905,3 kpx**, que é o que a régua devolve, e
   a nota guarda o 1 912,4 como história. Hoje está invertido.
6. **Feche `test_field_eval`** — remedindo os quatro relatórios numa **árvore limpa**, que é o
   caminho que o próprio relatório nomeia e não seguiu. *Alvo: a suíte do tronco volta a 3
   reprovações. A conta de que a remedição não move nada já está feita: 1 080 métricas, 0
   diferentes.*
7. **A marca da FEN vai para o lado em que há texto fora**, e volta para a lista de abertos. *Alvo:
   com o cursor no fim, a marca está à esquerda; com os dois lados fora, nos dois. Hoje
   `qt/rotulo.py:229` só sabe desenhar à direita.*
8. **`Motivo` legível a 1920**, e de volta à lista de abertos. *Alvo: 0 de 27 pedindo mais largura
   nas três larguras — hoje 17 / 24 / 25 de 27.*
9. **A grade do ícone fecha em 12 de 12**, e o paginador de quatro botões usa uma linguagem de seta
   com tinta dentro de ±20 %. *Hoje 10 de 12, e 11,2 %–48,5 % (124,7 %).*
10. **A fronteira do portão de execução encolhe para o que ela cobre**, e `_thread.start_new_thread`
    e `multiprocessing.Process.start` entram na interceptação. *Alvo: `sab_c11` passa de 1 de 4 a
    4 de 4, e a sabotagem entra no repositório do arnês como a C5, a C7, a C8 e a C9 entraram.*
11. **Um separador só.** *Alvo: 4 de 4 lugares com `" · "`, e uma sexta regra no censo tipográfico
    que o cobre — hoje 10 × `·` contra 4 × `|`, dois deles desenhados em toda pele e largura.*
12. **A Estudo e a Revisão redistribuem a sobra acima de 1920.** *Alvo: o maior vazio do painel não
    cresce com a janela — hoje a Revisão vai de 394,0 kpx a 1920 para **3 104,2** a 3840. O
    Resultado, no mesmo produto, faz o contrário (118,7 → 43,3), então é escolha e não fatalidade.*
13. **Nomeie a terceira E/S de disco na thread da janela**: `sqlite3.Connection.execute` a 37–38 ms
    dentro de `janela.py:1763 _atualizar_abas`, que aparece na pilha do pior nas minhas três
    execuções e não está em nenhum dos dois documentos. *Alvo: a lista de caminhos de E/S declarada
    cobre os que o perfil nomeia — hoje cobre três de quatro.*
14. **Itens 6, 7, 10, a tinta dos ícones e o bloqueio > 16 ms** continuam abertos com os números de
    sempre, declarados sem atenuação. Nenhum deles precisa fechar para eu aprovar.
15. **`bloqueio.py` para de reescrever a sessão de quem o roda.** *Alvo:
    `JanelaPrincipal(caminho_do_estado=capture.estado_de_medicao(...))` nas duas construções
    (`bloqueio.py:780` e `:798`) — hoje são as únicas duas sem o argumento —, e a certidão de
    higiene passa a nomear `data/janela.json`, que é o estado da janela Qt (`qt/janela.py:178`) e
    não só o `data/app_tkinter_state.json` do Tk.*
16. **Higiene de arnês**: `caissa.ui.audit.execucao --saida` deixa de ter padrão em
    `benchmarks\reports\ui\`, e o cabeçalho do portão de contraste deixa de dizer "nas duas peles"
    quando percorre duas polaridades × duas densidades.

---

## §8 — Como reproduzir

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONPATH=<suite>\src;<tronco>\src
set PYTHONDONTWRITEBYTECODE=1
set C11=benchmarks\reports\critique\ui\c11

:: o BLOQUEANTE
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe %C11%\c11_dialogos.py classica     :: 10 sem nome + 1 sem papel
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe %C11%\c11_dialogos2.py             :: janela principal: 0 sem nome
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe %C11%\c11_dialogos_prova.py        :: 11 -> 0 com nomear_tudo
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe %C11%\c11_dialogos_censo.py        :: 12 QDialog; dialogos/legenda/paleta: 0 setAccessibleName

:: portoes -- --saida SEMPRE para %C11%  (o de execucao tem padrao na pasta do construtor!)
-m caissa.ui.audit.teclado   --pdf "...\1937 Kemeri.pdf" --saida %C11%\gate_teclado :: 216/240/360 PASSOU x3
-m caissa.ui.audit.contraste --saida %C11%\gates          :: 300 / 220 / 0; 3,27 e 3,03
-m caissa.ui.audit.progresso --saida %C11%\gates          :: 8 indicadores, 13 operacoes, 0 invisiveis
-m caissa.ui.audit.execucao  --pdf "..." --saida %C11%\gates  :: 5 aberturas / 9 acoes, PASSOU
-m caissa.ui.audit.bloqueio  --pdf "..." --saida %C11%\gates  :: 3x -> 207 / 212 / 205 ms, REPROVOU

:: a largura da medicao -- as duas perguntas da ordem de servico
%C11%\c11_largura_da_medicao.py   :: 4a pele alcanca o portao? sim. densidade? 3 de 6 arranjos medidos
%C11%\c11_guarda.py               :: sem a fita em capture.PELES -> o teste FALHA (guarda estrutural)
for %%D in (compacta confortavel) do (set CVOFF_DENSITY=%%D & -m caissa.ui.audit.teclado --pele ...)
set CVOFF_DENSITY=confortavel & <c10>\c10_icones_da_janela.py   :: fita 32 px, amplitude 2x17 px

:: as provas de vida do construtor, rodadas por mim (editam o tronco e restauram; SHA-256 conferido
:: por mim ANTES e DEPOIS: qt/fita.py 1f27fac6...4a, qt/rodape.py 8f45d98e...26)
<c10>\c10_prova_de_vida.py        :: sem nome -> 90 acusados; glifo de volta -> 6 glifos
<c10>\c10_faixa_tardia.py         :: nunca troca de modo -> 4 bloqueantes; tique de 40 ms -> 0
%C11%\c11_faixa_250ms.py          :: tique de 250 ms > ASSENTAR_MS -> 4 bloqueantes (lado seguro)

:: sabotagens do portao de execucao
-m caissa.ui.audit.execucao --sabotagem <c10>\sab_c9  --saida %C11%\gates :: NAO EXECUTAVEL (QtConcurrent)
-m caissa.ui.audit.execucao --sabotagem <c10>\sab_c9x --saida %C11%\gates :: 8 de 8, 4 calados
-m caissa.ui.audit.execucao --sabotagem <c10>\sab_c10 --saida %C11%\gates :: 8 de 8, 5 calados
-m caissa.ui.audit.execucao --sabotagem %C11%\sab_c11 --saida %C11%\gates :: 1 de 4  <<< a fronteira

:: instrumentos deste ciclo
%C11%\c11_glifo_em_qualquer_lugar.py <pele> [densidade] :: 0 glifos fora do alcance do censo
%C11%\c11_texto_cortado.py            :: 0 em 3 peles x 3 larguras
%C11%\c11_ritmo_da_fita.py fita 1366  :: 24 botoes, 3 filas, 0 cabecalhos visiveis, 5 acessiveis
%C11%\c11_alinhamento_da_fita.py 1366 :: topos [0,6,49,55], alturas [31,43]
%C11%\c11_cor_no_cromo.py             :: 210 graus apenas, 0,036-0,084 % do cromo, nas 3 peles
%C11%\c11_casas_do_tabuleiro.py <pele>:: Estudo 73,000 (fechou); Resultado 87,125 / 83,125 / 81,125
%C11%\c11_zoom.py <png> x0 y0 x1 y1 [fator] [nome]

:: instrumentos anteriores, rodados sem alteracao (conferido antes que nao gravam)
<c10>\c10_icones_da_janela.py   :: 0 glifos nas 3 peles; 12 grades, caixa unica em 10
<c10>\c10_estado_morto.py       :: 3,66 / 3,27 / 3,66 : 1;  1 de 26 nas tres
<c10>\c10_orfas.py [--sem-conserto] :: 0 de 18  /  6 de 18
<c10>\c10_vazio_na_tela.py      :: 12 linhas por pele, 0 nao desenhados, 0 duplicados
<c10>\c10_sem_torch.py          :: 7 de 7 na janela, 4 de 4 na rede
critique\ui\c5\c5_vazios.py <png..>       :: 1920 identico a decimal; 4K: Dataset 1 905,3
critique\ui\c9\c9_tipografia_na_tela.py   :: 858 strings, 0 faltas
critique\ui\c7\c7_icones_da_janela.py     :: 0 glifos
ui\c6\c6_aberto.py                        :: 29 botoes em 4-6 filas; Motivo 17/24/25 de 27
ui\c8\c8_vazio_na_tela.py                 :: 30 de 30 DESENHADO=sim

:: suites
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly
   :: 4 failed, 4485 passed, 2 skipped, 4536 subtests em 318,05 s -- as mesmas quatro
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests\test_field_eval.py -q -p no:randomly
   :: 1 failed, 100 passed, 142 subtests -- os 4 relatorios, os 3 modulos
.venv\Scripts\python.exe -m pytest tests\unit\ui -q                :: 161 passed
.venv\Scripts\python.exe -m pytest tests -q --ignore=tests\integration\test_packaging.py
   :: 3049 passed, 1 skipped, 0 failed em 746,02 s -- o mesmo pulo (test_fonts.py:333, Brotli)
```

Artefatos meus, todos em `benchmarks\reports\critique\ui\c11\`: os doze instrumentos, a árvore
`sab_c11\`, `gate_teclado\` e `gates\` (os JSON dos portões), `sha_antes.txt`, `tronco_run1.txt`,
`nossa_sem_packaging.txt` e os recortes `z11_*.png`. **Nada fora desta pasta e deste documento foi
escrito por mim** — com a exceção declarada na Nota de procedimento, o JSON que o padrão de
`--saida` do portão de execução gravou em `benchmarks\reports\ui\` e que eu movi para cá.

---

## §9 — Veredito

**REPROVADO — por um defeito, e ele é a metade do produto que nenhum portão desta frente abriu.**

Este é o ciclo em que o bloqueante fechou de verdade e a guarda contra a recaída ficou de pé. O
glifo saiu de todos os botões da fita, em todas as peles e nas duas densidades, e eu o procurei
onde o censo não olha — rótulo, cabeçalho, item de tabela, item de menu, aba — e não o achei. O
nome acessível entrou, e a prova de vida acusa **90** quando ele sai. **A guarda de largura é
estrutural, e eu a testei por mutação e não por leitura**: uma quarta pele registrada em
`ui/pele.PELES` chega sozinha ao portão, e tirar a `fita` da captura derruba o teste. O estado
morto passou de 1,88:1 para 3,27:1 e o olho vê a diferença. `determinado` deixou de ser uma
consulta de duas entradas e sobrevive a um tique três vezes maior que a folga dele. A régua de
threads trocou de forma e passou a dizer `NÃO ATRIBUÍDA` em vez de calar. A suíte do tronco fecha
campo a campo, 161 de 161 em `tests/unit/ui`, e **zero texto cortado** em nove combinações de pele
e largura — uma régua que ninguém tinha escrito.

E os dois julgamentos que a ordem de serviço mandou fazer caem, os dois, do lado do construtor.
Publicar 1 905,3 ao lado de 1 912,4 em vez de escolher em silêncio é escrituração honesta — só está
na ordem trocada, e o número que reproduz é o meu, que é o dele. Recusar a remedição de
`test_field_eval` porque ela reescreveria dado de campo de outra frente e gravaria `dirty: true`
sobre um `dirty: false` publicado **não é um teste racionalizado**: o teste não foi tocado, a
afirmação foi paga com **1 080 métricas comparadas e 0 diferentes**, medidas com a ferramenta que o
próprio teste nomeia, num arquivo temporário. É a decisão certa. Falta fechá‑la, e o caminho é o
que o próprio relatório escreveu e não seguiu — remedir numa árvore limpa.

Não aprovo porque o portão que publica **`0 sem nome`** percorre `janela.abas` — as seis abas da
janela principal — e o produto tem **doze `QDialog` que nenhum portão desta frente jamais abriu em
onze ciclos**. Rodada a régua **do próprio portão** em seis diálogos que o usuário alcança pelo
menu e por atalho, ela devolve **11 controles sem nome acessível**: o campo onde se digita o
comando na **paleta de comandos**, aberta por `Ctrl+Shift+P` — a superfície que existe para quem
usa o teclado —, e **dois `QLineEdit` sem nome lado a lado** em `Achar e substituir`, de modo que
quem não vê a tela não distingue "Achar" de "Trocar por". Na janela principal, a mesma régua acha
**0 sem nome em 15 campos de texto**.

É o defeito nº 1 do **ciclo 1** desta frente, e é pior que o daquele ciclo: um `◀` pelo menos
anuncia alguma coisa; estes não anunciam nada. E o conserto **já existe no produto, com a decisão
escrita**: `qt/acessibilidade.nomear_tudo`, cujo docstring antecipa este defeito palavra por
palavra — *"a vigésima primeira, o campo que o próximo item acrescenta, nasceria muda"*. Ele é
chamado **uma vez em todo o produto**, em `qt/janela.py:361`, dentro do `__init__` da janela
principal; todo diálogo nasce depois e nunca é varrido. Chamei‑o à mão nos seis: **11 → 0**, com os
nomes certos (`Achar`, `Trocar por`, `Atalhos de teclado`).

Os nove instrumentos cegos anteriores erraram a **regra**. O décimo — o do ciclo 9 — mediu **uma
pele de três**. Este mede **uma janela de treze**, e é a mesma cegueira num eixo que ninguém tinha
pensado em olhar: não *qual aparência*, mas *qual janela*. O ciclo 10 consertou a largura no eixo
pele e a consertou estruturalmente, o que é a melhor forma; falta apontar a mesma disciplina para
a superfície. Feito o item 1 do §7 — a varredura que alcança todo diálogo e o portão que os
percorre lendo a lista do produto —, **aprovo**. Os quinze itens restantes são desenho, medida e
disciplina de instrumento; nenhum deles põe na tela um controle que o leitor de tela não sabe
nomear.
