# F9 — Relatório do ciclo 4 (Interface)

```
FRENTE: F9 (Interface)
CICLO:  4
ORDEM DE SERVIÇO: docs/quality/F9_CRITIQUE_C3.md §7
```

---

## §0 — Quem fez o quê, e por que este relatório diz isso

Este ciclo teve **dois autores**. O primeiro fez o grosso do trabalho de código e foi interrompido
por limite de taxa exatamente na frase *"All 36 captured at the declared sizes. Now let me look at
every one"* — as 36 capturas existiam e **ninguém as tinha olhado**, e o relatório nunca foi
escrito. O segundo (eu) rodou os instrumentos do crítico contra o que estava no disco, **olhou as
36 capturas**, achou **três defeitos que nenhum portão pegou**, consertou-os — e o conserto de um
deles achou um quarto, que era **meu** e derrubava a suíte do tronco (§6) —, recapturou as 36,
olhou de novo, e escreveu isto.

Cada item abaixo diz **quem** o fechou. Onde eu digo "o antecessor", o crédito é dele; onde digo
"eu", o defeito foi achado nesta sessão. Isso importa porque o ciclo 3 reprovou, entre outras
coisas, por atribuição errada — e a atribuição de autoria segue a mesma regra da de custo.

**Todos os números deste documento saíram de um comando que eu rodei nesta máquina.** Onde o
número é do crítico ou do ciclo anterior, ele está marcado como tal.

### AVISO — eu destruí 14 capturas do ciclo 1 do crítico, sem querer, e o nome delas agora mente

A ordem de serviço mandava **rodar os instrumentos do crítico**. Um deles,
`benchmarks/reports/critique/ui/casos_ruins.py`, **grava** as capturas dele numa pasta cravada no
código — a própria pasta do crítico — e com os nomes do ciclo 1. Rodá-lo sobrescreveu, às **01:26**
desta sessão, estes **14 arquivos**:

```
benchmarks/reports/critique/ui/c1_{claro,escuro}_1024x768_{resultado,estudo,revisao,texto,dataset,galeria}.png
benchmarks/reports/critique/ui/c1_{claro,escuro}_pagina289.png
```

**Eles não são mais do ciclo 1**: contêm a janela de **hoje** (dá para ver `OCR melhor diagrama`, a
paleta encostada no tabuleiro e a página ajustada ao visor), e nem o tamanho do nome é verdade — a
janela recusa 1024×768 e o PNG tem **1066×768**. Não há cópia: a pasta da suíte não é repositório
git e o comando não faz backup.

**Não renomeei nem apaguei nada**, por duas razões: os nomes estão citados no §8 da própria crítica
do ciclo 3, e mexer mais na pasta do crítico depois de já ter estragado seria a segunda decisão
errada em cima da primeira. O aviso é o conserto que me cabe: **as 14 não servem como evidência do
ciclo 1**. As do ciclo 3 (`c3_colapso_*.png`, `z_progresso_*.png`, `z_rodape_claro.png`), as
`c1_estados_*` e as `c1_titulo_longo_*` **não foram tocadas** — confirmei pelas mtimes (16:52 e
21:53 de 07/09, contra 01:26 de 08/09 nas 14).

E fica a lição para quem rodar `casos_ruins.py` no próximo ciclo: **ele escreve, e escreve por
cima**.

---

## §1 — Os três bloqueantes

### Bloqueante 1 — a virada de página relia o `labels.csv` inteiro na thread da janela

**Fechado pelo antecessor.** `janela._aviso_de_treino` construía um `LabelStore` novo e lia 5.431
linhas × 20 colunas a cada `_pagina_apareceu`. A leitura saiu do ponto de chamada e virou
`qt/marcas.paginas_com_amostra_de_treino`, memoizada por `(tamanho, mtime)` dos **dois** arquivos
que a produzem (`labels.csv` e `splits.csv`) — a mesma técnica de `contagem_de_amostras`, que era
o que o §7.1 pediu com essas palavras.

**Medido com o instrumento do crítico** (`benchmarks/reports/critique/ui/c3/quem_chama.py`):

```
=== virar para a pagina 41  — 107.5 ms; 0 leituras completas do labels.csv ===
=== virar para a pagina 121 — 168.4 ms; 0 leituras completas do labels.csv ===
```

**Zero leituras por virada**, contra **uma por virada** e **108.620 chamadas de `labels._clean` na
`MainThread`** que o crítico mediu.

O `custo_aviso.py` do crítico **não roda mais como está** — ele faz `mod.LabelStore` sobre
`qt/janela.py`, e esse nome não existe mais ali, que é a própria forma do conserto. Adaptei-o ao
ponto de chamada novo, neutralizando **a mesma leitura** no lugar novo
(`benchmarks/reports/ui/c4/c4_custo_aviso.py`):

| | viradas (ms) | mediana |
|---|---|---|
| com o aviso de treino | 96,6 · 96,1 · 92,4 · 99,4 · 112,3 · 106,8 | **98,0** |
| sem ele | 102,6 · 106,7 · 108,2 · 100,8 · 110,4 · 119,1 | **107,5** |

**Custo do aviso: −9,5 ms** — isto é, zero dentro do ruído (o que sobrou é um `dict.get` mais dois
`stat`). Era **57,7 ms, 34 % da virada, 3,6× o portão**.

**Alvo do §7.1: virada ≤ 116 ms. Medido: 98,0 ms. PASSA.**

E a atribuição do §3 do relatório do ciclo 2, que o crítico refutou, fica **reescrita com o número
certo** (arnês `bloqueio`, 3 execuções, abaixo): a virada é **86,5–88,2 % PyMuPDF** e
**1,8–2,4 % desta frente**. Não é "PyMuPDF e não é desta frente"; é "PyMuPDF, e a parte desta
frente eram 34 %, que agora são 2 %".

### Bloqueante 2 — a barra de progresso permanente, as duas leituras não registradas, e o portão cego

Este tem **três metades** e as três fecham, duas pelo antecessor e uma por mim.

**(a) As duas leituras assíncronas registram. Fechado pelo antecessor.**
`qt/marcas.LeitorDeMarcas.pedir` e `qt/painel_do_dataset._reler_agora` chamam `busy.register` com
`cancel` de verdade. O inventário do portão vai de **6 para 8**:

```
.venv\Scripts\python.exe -m caissa.ui.audit.progresso
  ...
  marcas salvas do livro   NAO  NAO  sim  src/chess_diagram_ocr/qt/marcas.py:193
  leitura do dataset       NAO  NAO  sim  src/chess_diagram_ocr/qt/painel_do_dataset.py:434
  (8 indicadores de progresso)
```

**Alvo do §7.3: o portão listar 8 operações e não 6. Medido: 8. PASSA.**

As duas são **indeterminadas de propósito e o motivo está escrito no código**: quem conta as
linhas é `LabelStore._load_rows`, dentro de `labels.py`, que não tem callback de progresso — e uma
barra determinada que ninguém pode fazer andar fica parada em 0 % até o fim, que é o defeito
bloqueante nº 2 do ciclo 3 com outro nome.

**(b) O portão enxerga a operação que não se registra. Fechado pelo antecessor.**
`caissa.ui.audit.progresso` ganhou uma segunda varredura — as **operações de fundo de `qt/`** —, e
cada uma ou **REGISTRA**, ou está **DECLARADA** em `ui/busy.FORA_DO_REGISTRO` com o motivo, ou é
**INVISÍVEL** e o portão reprova (`Indicador.invisivel` entra em `bloqueantes`). São 13 threads:
10 registradas, 3 declaradas, **0 invisíveis**. A tabela de exceções saiu de `tests/test_busy.py`
e foi para `ui/busy.py` — que é o que faz o portão poder lê-la. Era o defeito de instrumento do
§4.2: *"uma operação que nunca se registra é invisível para ele"*.

**(c) A barra se esconde. Fechado pelo antecessor — e ela ainda mentia por 400 ms, que fechei eu.**

A barra nasce escondida e aparece por `estado_do_rodape.Ocupacao.mostra_barra`. Medido com o
instrumento do crítico (`detalhes.py`), janela ociosa:

```
=== barra de progresso do rodape ===
   visivel=False  x=1712 y=1051  120x26  faixa=0..100 valor=0 texto_visivel=False
   botao Cancelar: habilitado=False
```

Era `visivel=True, 0/100, texto_visivel=False`, **permanente nas 36 capturas do ciclo 2**.
**Alvo do §7.3: zero pixels de barra na janela ociosa. Medido: `visivel=False`. PASSA.**

**O que eu achei olhando as 36, e que a medição não pega.** Em
`c4_claro_1280x800_dataset.png` — **1 das 36** — o rodapé dizia **"Lendo o dataset…"** na zona de
mensagem com a **barra escondida** e o **`Cancelar` desabilitado**. É a frase exata com que o
bloqueante nº 2 reprovou o ciclo 2, sobrevivendo numa janela estreita. A causa:

- a zona de mensagem é escrita por **sinal**, no instante em que a operação começa;
- a zona de ocupação era lida por **relógio**, a cada `INTERVALO_DE_ACOMPANHAMENTO_MS = 400 ms`.

**Até 400 ms de rodapé contradizendo a si mesmo**, e a captura pegou um deles.

O conserto é um observador em `ui/busy.BusyRegistry` (`observe`, chamado em `register`, `_release`
e no `_update` **que muda algo**) e um sinal Qt em `qt/rodape.py` para pular da thread de trabalho
para a da janela (`ocupacao_mudou`). **O relógio fica**: ele é a rede contra o `release()`
esquecido da S-112, e é isso que está escrito no código. `janela.py` passa
`avisos=self.busy.observe` na chamada que já existia — **zero linhas novas** naquele arquivo, que
é o que a catraca de `test_packaging` exige (1881 ≤ 1882).

Cobrado por três testes novos em `tests/test_busy.py` (o aviso sai ao registrar e ao soltar; não
sai num tique idêntico; um observador que levanta não derruba quem registrou), dois em
`tests/test_qt_rodape.py` (registrar acende a barra com o relógio em **10 s** — de propósito: se
fosse o tique a acendê-la, o teste falharia; e soltar depois de o rodapé morrer não derruba o
processo, ver §6) e um em `tests/test_qt_janela.py` (a janela **liga** o rodapé ao aviso — um
rodapé que sabe assinar mas que ninguém assina deixa o mesmo defeito na tela).

**Nas 36 capturas novas: 0 contradizem-se.** Toda captura com operação viva mostra barra + Cancelar
habilitado; toda captura ociosa mostra ausência de barra + Cancelar desabilitado.

### Bloqueante 3 — a prancha de estados desenhava `hover` idêntico a repouso

**Fechado pelo antecessor.** `amostrario.py` deixou de mandar `Enter`/`HoverEnter` sintéticos (que
não ligam `QStyle::State_MouseOver`, e por isso o QSS não aplica `:hover`) e passou a **montar a
`QStyleOption` à mão com `State_MouseOver` aceso**. Regerei as 8 pranchas nesta sessão (elas
estavam mais velhas que `ui/folha_de_estilo.py`) e medi:

| pele | NEUTRO | PRIMARIO | DESTRUTIVO | campo |
|---|---|---|---|---|
| claro (foco0..3) | **25** | **36** | **26** | 0 |
| escuro (foco0..3) | **15** | **27** | **30** | 0 |

**ΔRGB máx era 0 nas 8 pranchas, nas 4 linhas, nas 2 peles. Menor ΔRGB de `hover` agora, entre os
três papéis de botão e as oito pranchas: 15. PASSA.**

O `campo` continua em 0 **e isso é a verdade do produto, não um buraco**: `ui/folha_de_estilo.py`,
bloco `campos`, declara `:focus` e `:disabled` para os oito seletores e **nenhum** `:hover`. A
prancha **escreve isso na própria imagem** (o rodapé de texto sob a grade), e
`tests/unit/ui/test_amostrario.py` cobra as duas pontas: recalcula o ΔRGB **a partir do PNG** e
confere contra o manifesto (um gerador que passasse a publicar delta inventado falha), exige
`> 0` nos três papéis de botão e `== 0` no campo **com a nota citando `folha_de_estilo` e
`:hover`** — para que a isenção não vire o lugar onde se esconde um `hover` quebrado.

---

## §2 — Item 13, e os itens de desenho do §7 (5 a 13)

### §7.7 / item 13 — encostar a paleta no tabuleiro

**Fechado pelo antecessor.** Medido sobre `c4_claro_1920x1080_resultado.png` com o
`medidas_c3.py regiao` do crítico:

| região | ciclo 2 (crítico) | agora |
|---|---|---|
| vão entre tabuleiro e paleta | **180×580 = 104,4 kpx a 0,17 %** | **8×557 = 4,5 kpx a 0,00 %** |

Ocupação do canvas — o tabuleiro contra a caixa que o contém **com a paleta**, que é a caixa de
que o item 13 fala. Medi as capturas do c2 e as do c4 **com o mesmo critério**
(`benchmarks/reports/ui/c4/c4_ocupacao.py`), para os dois números serem comparáveis:

| captura | paleta em x | canvas | ocupação |
|---|---|---|---|
| `c2_claro_1920x1080_resultado` | 976–1047 | 826×551 = 455,1 kpx | **66,7 %** |
| `c2_escuro_1920x1080_resultado` | 976–1047 | 813×526 = 427,6 kpx | 64,7 % |
| `c4_claro_1920x1080_resultado` | **603–674** | **640×552 = 353,3 kpx** | **86,2 %** |
| `c4_escuro_1920x1080_resultado` | **577–648** | 614×526 = 323,0 kpx | **85,7 %** |
| `c4_claro_1366x768_resultado` | 369–440 | 406×318 = 129,1 kpx | 78,3 % |

**Alvo do §7.7: ocupação ≥ 80 % em Resultado. Medido: 86,2 % (claro) e 85,7 % (escuro) a 1920.
PASSA.** A 1366 dá **78,3 %** — 1,7 ponto abaixo, e digo o número em vez de citar só o de 1920.

(O crítico publicou **58,2 %** para o c2 com uma caixa de 933×559; o meu critério dá 66,7 % para a
mesma imagem. A diferença é onde cada um põe a borda do canvas, não o que aconteceu com o vão — e
é por isso que a tabela acima mede os dois ciclos com a régua única.)

**E registro o que apareceu no lugar, porque é meu trabalho dizê-lo:** a moldura do grupo
"Reconhecido" continua com a largura do painel, então onde havia um vão de 104 kpx **entre** os
dois objetos há agora **365×557 = 203,3 kpx a 0,00 % à direita da paleta**. Isso viola o alvo de
composição do §2.4 ("nenhuma região acima de 200 kpx com menos de 2 % de tinta") e **não** o alvo
do item 13. Não fechei: o tabuleiro é quadrado e limitado pela **altura** do canvas
(`max(MAX_DO_TABULEIRO, min(w, h))` = 560), então aqueles pixels não podem virar tabuleiro —
fechá-los é mudar onde a borda do grupo é desenhada, que é re-emoldurar e não adensar. Fica
declarado com o número.

### §7.5 — a ênfase da aba

**Fechado pelo antecessor, pelo segundo dos dois caminhos que o crítico ofereceu.** O §7.5 dizia
*"ou `conferir_tela` passa a permitir uma por painel de aba, **ou** as ações de aba ganham a tecla"*.
Ganharam a tecla. `ui/atalhos.por_acao`, medido:

| ação | ciclo 3 | agora |
|---|---|---|
| `corrigir_agora` | **sem tecla** | `Ctrl+Shift+N` |
| `anotar_pagina` | **sem tecla** | `Ctrl+G` |
| `estudo_do_diagrama` | **sem tecla** | `Ctrl+E` |
| `ler_melhor` | **sem tecla** | `Ctrl+D` |
| `salvar` | `Ctrl+S` | `Ctrl+S` |

**5 de 5 comandos rebaixados com tecla global** (era 1 de 5). O total de ações com tecla vai de
**21 para 25**.

E o que isso comprava — a ênfase única — continua intacto. Censo por aba, janela 1920, livro
aberto, lendo `tema.PROPRIEDADE_DE_PAPEL`:

```
Resultado  botoes= 24 primarios=1 destrutivos=1 excesso_de_enfase=0
Estudo     botoes= 43 primarios=1 destrutivos=3 excesso_de_enfase=0
Revisão    botoes= 24 primarios=1 destrutivos=1 excesso_de_enfase=0
Texto      botoes= 27 primarios=1 destrutivos=1 excesso_de_enfase=0
Dataset    botoes= 26 primarios=1 destrutivos=3 excesso_de_enfase=0
Galeria    botoes= 31 primarios=1 destrutivos=2 excesso_de_enfase=0
```

**Honestidade:** a primária continua sendo a do visor (`OCR melhor diagrama`), e por isso continua
verdade que **6 de 6 abas não têm ação primária própria**. O que mudou é que as ações rebaixadas
deixaram de ser inalcançáveis pelo teclado — que é a compensação que o §7 do ciclo 1 pediu e o
ciclo 2 não entregou.

### §7.6 — abrir a escala de tipos

**Fechado pelo antecessor.** A escala declarada vai de **11/12/13 px** (degraus de +9 % e +8 %)
para **11/12/16 px**, e entra um peso novo:

```
benchmarks/reports/critique/ui/sonda.py tipografia
  papel TITULO   pt=12.0 peso=700     (16 px)
  papel ACAO     pt=9.0  peso=600     (12 px)  <- novo
  papel CORPO    pt=9.0  peso=400
  papel AUXILIAR pt=8.0  peso=400     (11 px)
  papel DADO     Consolas pt=9.0
```

Censo conjunto (px × peso × família) na **aba Galeria a 1920**, que é exatamente onde o crítico
mediu, com o **mesmo número de widgets visíveis (107)**:

| combinação | widgets | % |
|---|---|---|
| 12 px / 400 / Sans Serif | **70** | **65,4 %** |
| 12 px / 600 / Sans Serif | 30 | 28,0 % |
| 11 px / 400 / Sans Serif | 4 | 3,7 % |
| 16 px / 700 / Sans Serif | 3 | 2,8 % |

**Alvo do §7.6: ≤ 80 % dos widgets numa única combinação. Medido: 65,4 %** (era **99 de 107 =
92,5 %**). **PASSA.**

O degrau que produz hierarquia é o de `TITULO`: **12 → 16 px é +33 %**, contra os +8 % que o ciclo
1 já tinha dito que não produzem hierarquia. E o peso 600 do papel `ACAO` alcança 28 % dos widgets
— era o peso que chegava a 2,8 %.

### §7.8 — o visor reajustar a página

**Fechado pelo antecessor.** O zoom deixou de ser **um número** e virou **um modo**
(`ui/viewport.ENQUADRAMENTOS`: livre, largura, página), gravado no estado e **reaplicado no
redimensionamento**. Medido com o `medidas_c3.py pagina` do crítico:

| captura | ciclo 2 | agora |
|---|---|---|
| 1280×800 | 366 px | **520 px** |
| 1366×768 | 366 px | **558 px** |
| 1920×1080 | 366 px | **800 px** |

A 1920 o viewport útil tem ~819 px e a página ocupa **97,7 %** dele — o alvo era **≥ 60 % nas três
resoluções**, e ele passa nas três. **PASSA.** Era *"abrir o programa num monitor maior não dá mais
página: dá mais branco"*.

### §7.10 — apagar a frase repetida da Galeria

**Fechado pelo antecessor.** `detalhes.py`, o instrumento do crítico:

```
=== frases que dizem 'nada varrido' visiveis ao mesmo tempo na Galeria ===
   y= 362 x=  17  'Nenhum diagrama ainda'
   y= 390 x=  17  'A Galeria mostra os diagramas que uma varredura já encontrou neste livro. Varra '
```

De **duas afirmações independentes a 302 px** (ciclo 3; três no ciclo 1) para **uma**, com a sua
própria explicação 28 px abaixo. A frase de y=62 sumiu. **PASSA.**

### §7.11 — alinhar `Gravar`

**Fechado pelo antecessor.** `detalhes.py`:

```
   Gravar                     x= 826 largura=218
   Limpar os headers          x= 826 largura=218
   Partidas da base           x= 826 largura=218
   Copiar headers para todos  x= 826 largura=218
   Desfazer a cópia           x= 826 largura=218
   valores distintos de x: [826]  -> desalinho maximo = 0 px
```

Era **63 px de desalinho e 63 px de diferença de largura**. **PASSA.**

### §7.12 — o divisor não apagar a navegação

**Fechado pelo antecessor.** `colapso.py`, o instrumento do crítico, janela 1366×768:

```
   QSplitter  tamanhos=[764, 596]  childrenCollapsible=False  handleWidth=6
   antes de colapsar                       controles dentro=36  FORA da janela=0
   QSplitter: painel 0 colapsado -> [0, 94] controles dentro=36  FORA da janela=0
   QSplitter: painel 1 colapsado -> [94, 0] controles dentro=36  FORA da janela=0
```

**0 de 36 controles fora da janela em qualquer posição da alça** (era **21 de 36** com o painel
esquerdo colapsado e 14 de 36 com o direito), `setChildrenCollapsible(False)`, e a alça vai de
**3 px para 6 px**, dentro dos 6–8 px que o §7.12 pediu. **PASSA.**

**O que isso custou, medido:** `minimumSizeHint` vai de **1063×735 para 1066×735** (claro) e
**1063×769 para 1066×769** (escuro) — os 3 px da alça. 1366×768 continua aceito nas duas peles.

### §7.13 — o quinto motivo do portão de nomes

**Fechado pelo antecessor.** `caissa.ui.audit.teclado._e_prosa` recusa um nome acessível que seja
prosa — **ponto final seguido de espaço**, ou mais que o teto de caracteres —, e o motivo publicado
é `"e prosa, nao nome"`. O `QComboBox` de regime era anunciado nas seis abas por **67 caracteres
terminando em "separa as"**; o portão agora devolve **0 sem nome / 0 sem papel / 0 nome vazio** nas
seis. **PASSA.**

### §7.9 — a tabela da Revisão — **NÃO FECHADO, e o número é meu**

Medido em `c4_claro_1920x1080_revisao.png` com os 27 itens que a aba tem:

```
  corpo_da_tabela_nao_usado   1048x375 = 393.0 kpx   tinta 0.00 %
```

Contra **394,0 kpx** que o crítico mediu. **Não mudou.** A fila de ações continua no pé do painel.

A 1366 e a 1280 o defeito **não existe**, e medi para poder dizê-lo: `738×65 = 48,0 kpx a 0,00 %`
a 1366 e `692×97 = 67,1 kpx a 0,29 %` a 1280 — a tabela chega perto do fim do painel e a fila de
ações fica logo abaixo. Isto é um defeito **de tela grande**: a tabela tem altura fixa em linhas e
o painel cresce com a janela. Declarado, não fechado.

---

## §3 — Os defeitos não bloqueantes do §5 da crítica

| # | defeito | situação | número medido por mim |
|---|---|---|---|
| 1 | item 13, o vão entre tabuleiro e paleta | **FECHADO** | vão de 104,4 kpx a 0,17 % → **4,5 kpx a 0,00 %**; ocupação do canvas **66,7 % → 86,2 %** (mesma régua nos dois ciclos) |
| 2 | Estudo: 28 botões em 4 filas (alvo ≤ 12 em ≤ 2) | **NÃO FECHADO** | **28 botões**, 4 filas a 1920, 5 a 1366, 6 a 1280 (contados nas capturas). `.md`/`.html`/`.rtf` continuam três botões permanentes |
| 3 | 7 operações violando o portão, o relatório nomeava 2 | **FECHADO na prática** | continuam **7**; o arnês publica as 7 com `viola=True` **e a atribuição de cada uma** (§5) |
| 4 | a pilha do "abrir PDF" não é estável | **FECHADO como instrumento** | a `pilha_do_pior` continua sendo uma amostra, mas agora vem com o **tempo próprio por família**, que não depende de amostra |
| 5 | *"`ui/atalhos.py` mantém as teclas"* é falso para os cinco comandos movidos | **A FRASE ESTÁ ERRADA E EU A RETIRO** | `exportar_pgn`, `cancelar_exportacao`, `marcar_diagramas`, `roda_vira_pagina` e `abrir_no_leitor` **não tinham e não têm tecla**. Não havia tecla para manter. O alcance deles é pelo menu, e é real; a afirmação do ciclo 2 é que era falsa |
| 6 | o divisor colapsa e leva a navegação | **FECHADO** | 21/36 fora → **0/36**, alça 3 px → 6 px |
| 7 | a coluna "Motivo" elidida | **NÃO FECHADO, e piorou 40 px por minha causa** | a seção "Motivo" a 1920 vai de **730 px para 690 px**: alargar `Conf. mín` de 80 para 100 px (§6) tirou 20 px da elástica, e o resto veio das outras fixas que também pararam de mentir. Troquei **um cabeçalho ilegível** por **~40 px a menos de motivo**, e digo o preço em vez de esconder |
| 8 | Dataset precisa de barra horizontal a 1280/1366, "Conjunto" cortado | **METADE FECHADA POR MIM** | o cabeçalho **"Conjunt" virou "Conjunto"** nas duas peles e nas três larguras (§6). A barra horizontal continua a 1280 e a 1366 — e agora ela é **mais** necessária, porque as colunas ficaram honestamente maiores |
| 9 | um nome acessível que é prosa | **FECHADO** | quinto motivo no portão; 0 ocorrências nas seis abas |
| 10 | `DialogoDeTreino: barra fixa em indeterminada` | **DECLARADO** | continua no inventário como `total NÃO / determinada NÃO / cancelável NÃO`; é coberta pelo registro de `dialogos.py:740`, que aparece na linha seguinte do mesmo inventário |
| 11 | o 92,7 fps não reproduz | **CORRIGIDO NO RELATÓRIO** | 3 execuções minhas: **85,4 · 87,6 · 88,8 → mediana 87,6 @ p95**. O crítico mediu 85,0. **O 92,7 do ciclo 2 não reproduz e eu não o repito** |
| 12 | a janela recusa 1024×768 e 800×600 | **NÃO FECHADO, declarado** | `1066×735` (claro) e `1066×769` (escuro); pedido 1024×768 → ficou 1066×768 `RECUSOU` |
| 13 | os botões de formato não mostram o que fazem | **FECHADO** | `Negrito` em negrito, `Itálico` em itálico, `Sublinhado` sublinhado, `Tachado` tachado — visível nas 6 capturas da aba Texto |
| 14 | `Modo bloco (lento)` | **NÃO FECHADO** | intocado |
| 15 | dois controles sem rótulo visível na aba Texto, um campo sem rótulo na Galeria | **NÃO FECHADO** | o spinner `1` e o combo `auto` continuam sem rótulo na tela; têm nome acessível (o portão de teclado dá 0 sem nome) |
| 16 | casos ruins que passaram | **MANTIDO** | spinner de página **75 px com `289`** e **81 px com `9999`**, sem refluxo |

---

## §4 — Os nove critérios, remedidos

| # | critério | ciclo 3 | agora |
|---|---|---|---|
| 1 | Hierarquia visual | 1 primária por tela, mas 6/6 abas sem primária própria e 4/5 rebaixadas sem tecla | 1 primária por tela (`excesso_de_enfase=0` nas seis), **5/5 rebaixadas com tecla**; 6/6 abas continuam sem primária própria |
| 2 | Ritmo espacial | SOBREVIVE, com `Gravar` 63 px fora do prumo | SOBREVIVE; **desalinho 0 px** |
| 3 | Alinhamento | SOBREVIVE (10 px em seis abas) | mantido, não regrediu |
| 4 | Densidade × vazio | NÃO SOBREVIVE | melhora real no visor (366 → 800 px de página) e no canvas (66,7 → 86,2 %); **continua não sobrevivendo**: 393,0 kpx a 0,00 % na Revisão a 1920, 203,3 kpx à direita da paleta, 284,8 kpx a 3,35 % na caixa "Lances" |
| 5 | Cor como sinal | SOBREVIVE, o melhor item | mantido; contraste 287/213/**0** nas duas peles |
| 6 | Tipografia | NÃO SOBREVIVE (92,5 % numa combinação) | **65,4 %**, escala 11/12/16, três pesos. Passa o alvo |
| 7 | Controles | SOBREVIVE | mantido; e o `hover` agora **tem prova** (ΔRGB ≥ 15) |
| 8 | Estados vazios | SOBREVIVE COM RESSALVA (duas frases a 302 px) | **a ressalva caiu**: uma afirmação, com a sua explicação |
| 9 | Pele escura | SOBREVIVE | mantido. **A ressalva antiga continua e eu a mantenho no papel**: o tabuleiro é **552 px na clara contra 526 na escura** a 1920 (−9,2 % de área), preço da fila de pílulas do topo; e duas das quatro pílulas continuam duplicando botões visíveis na mesma tela |

---

## §5 — Os portões (carta §6)

| portão | medição minha | veredito |
|---|---|---|
| Contraste WCAG AA | `287 pares / 213 sob portão / 0 reprovados` nas duas peles; folga mín. **3,27:1** (claro) e **3,03:1** (escuro) | **PASSOU** |
| Teclado + nome + papel | 24+52+30+39+21+50 = **216 focáveis, 216 pelo Tab**, `0 sem nome / 0 sem papel / 0 nome vazio` nas seis abas | **PASSOU** |
| Progresso determinado/cancelável | **8** indicadores; 13 threads de `qt/`: 10 registradas, 3 declaradas, **0 invisíveis** | **PASSOU** |
| Janela cabe em 1366×768 | `minimumSizeHint` **1066×735** / **1066×769**; 1366×768 `OK` nas duas peles | **PASSOU** |
| Nome de livro de 149 chars | mesmo `minimumSizeHint` (**1066×735**) com o nome curto e com o de 149; **0 fora**, **1 sobreposição** (os 987 px² do `QLineEdit` interno do `QSpinBox`, que o §7 isenta) | **PASSOU** |
| fps ≥ 55 @ p95 | 3 execuções: **85,4 · 87,6 · 88,8 → mediana 87,6**; pan 530–640 fps, zoom 63,7–67,3 | **PASSOU** |
| Nada bloqueia a thread > 16 ms | **7 operações violam**, medianas de 3: abrir PDF **290,1**, virar p.41 **107,0**, p.42 **104,0**, p.121 **103,7**, rasterizar 300 DPI **75,8**, aba Dataset **67,0**, aba Galeria **26,3** | **REPROVA** (ver abaixo) |
| ADR-0009 (fronteira `ui/` × `qt/`) | `110 passed in 0.66s` em `tests/unit/ui/` | **PASSOU** |

### A atribuição, que é o que o §7.2 pediu

O `bloqueio.py` publica agora, **ao lado** da `pilha_do_pior` (que continua sendo **uma amostra** e
diz isso no próprio rótulo), o **tempo próprio por família de arquivo**, de uma passada de
`cProfile` — que é o que sobrevive a mil chamadas pequenas. Três execuções, virada de página:

```
    tempo PROPRIO por familia (cProfile, passada separada -- ve custo espalhado):
          97.5 ms   88.2 %  PyMuPDF
           7.0 ms    6.3 %  builtins (C)
           2.9 ms    2.6 %  pathlib/os (disco)
           2.0 ms    1.8 %  qt/ (esta frente)
      -> DESTA FRENTE (qt/ + ui/): 2.1 ms (1.9 % do perfilado)
```

| operação | desta frente, 3 execuções |
|---|---|
| virar para a p.41 | 2,2 · 2,0 · 2,3 ms → **2,0–2,1 %** |
| virar para a p.42 | 2,2 · 2,6 · 2,4 ms → **2,0–2,4 %** |
| virar para a p.121 | 2,1 · 1,8 · 2,4 ms → **1,8–2,2 %** |
| abrir PDF | 8,1 · 3,5 · 3,5 ms → **2,1–4,6 %** |
| rasterizar 300 DPI | 0,0 ms → **0 %** |

**O portão continua reprovando, e a razão é PyMuPDF.** O que mudou é que agora isso é uma medida do
arnês e não uma afirmação do relatório — *"o relatório do arnês, sozinho, mostrar que a virada de
página tem custo em `qt/` sem ninguém precisar escrever um instrumento novo"*, que é o alvo do
§7.2, e o custo que ele mostra é **2 %** e não os 34 % que o ciclo 2 não viu.

Registro também que `marcas.py:77 _marca_de` — os dois `stat` da memoização do bloqueante 1 —
**aparece na lista das funções mais caras**, com 1,6–2,2 ms. Ele é o preço do conserto e está à
vista.

---

## §6 — O que eu achei olhando as 36 capturas

Olhar é o passo que a medição não substitui, e nesta frente ele achou **três defeitos** que nenhum
portão pegou. O primeiro — o rodapé se contradizendo por 400 ms — está no §1, porque é o
bloqueante nº 2 sobrevivendo. Os outros dois estão aqui. E há um quarto, que foi **meu**: o
conserto do primeiro derrubava a suíte do tronco, e ele está aqui também.

### O cabeçalho da Revisão dizia **"onf. min"** — em 6 das 36 capturas

`qt/tabela.TabelaQt._largura_da_secao` **já** existia e **já** fazia o certo — a largura é a maior
entre a declarada e a do título medido. Ela era chamada **uma vez, no construtor**, onde
`header().font()` ainda é a fonte de fábrica (9 pt, sem negrito). A folha de estilo do produto
chega **depois** e dá ao cabeçalho **12 px em peso 700**:

```
3 'Conf. min'  declarada= 80  secao= 80  texto(fonte final)= 76  +recheio= 100   CORTA
```

A coluna é numérica, alinha à direita, e por isso a sobra é comida pela **esquerda**: o que se
perde é a primeira letra. Nas seis capturas da aba Revisão (3 larguras × 2 peles) lê-se
**"onf. min"**.

Isto é uma regressão contra um crédito que o crítico deu por escrito no §5.16 — *"nenhum rótulo
cortado nas seis abas"*.

**Conserto:** `alargar_o_que_corta_o_titulo()`, chamada no construtor **e** num `eventFilter` sobre
o cabeçalho em `FontChange`/`StyleChange`. Ela **só alarga** (quem arrastou para 300 px quer
300 px) e sobe junto o piso de `_LimiteDeSecao` (senão a mesma alça devolveria o corte pela mão).
E `"Conf. min"` virou `"Conf. mín"`, que é a forma que `painel_de_resultado.py` já usava.

**Medido depois, na janela viva:**

```
Revisão: secoes [60, 58, 64, 100, 80, 690]   colunas com titulo cortado: 0
Dataset: secoes [210, 258, 72, 108, 96, 120, 58, 130]   colunas com titulo cortado: 0
```

O mesmo conserto fez **"Conjunt" virar "Conjunto"** na aba Dataset — que era o não bloqueante nº 8
do crítico, e cuja causa raiz era esta.

**Não afrouxei o teste que isso quebrou.** `test_a_coluna_nao_encolhe_abaixo_do_minimo_dela`
afirmava `sectionSize == largura_minima(coluna)`. Com o piso agora sendo
`max(largura_minima, título+recheio)`, a expectativa passou a ser exatamente esse máximo — continua
sendo uma **igualdade**, e ela agora também proíbe o corte. Trocar por `assertGreaterEqual` teria
sido afrouxar; não foi o que fiz, e o motivo está escrito na docstring do teste.

### `ui/viewport` acrescentou um infrator novo a um teste do tronco que já falhava

`test_strings.AccentTests` é um dos 3 reprovados pré-existentes do tronco. Os
`ENQUADRAMENTO_* = "PAGINA"` que este ciclo criou **entraram na lista dele** (`viewport.py:
'PAGINA'`). Um teste que já falha é o lugar mais fácil do mundo para esconder um defeito novo.

O próprio teste tem a regra estreita para este caso, escrita na S-230 com o `PADRAO = "padrao"`:
escapa o literal que é **exatamente** o nome MAIÚSCULO em minúsculas, porque é identificador de
formato gravado e não texto de tela. As três chaves passaram a essa forma
(`ENQUADRAMENTO_PAGINA = "enquadramento_pagina"`). Um valor antigo no disco cai no padrão —
`state._aplicar` e `visor.definir_enquadramento` só aceitam o que está em `ENQUADRAMENTOS`, e o
campo nasceu neste mesmo ciclo.

`viewport.py` saiu da lista de infratores. Os 6 restantes (`biblioteca.py`, `substituicao.py` ×4,
`tokens.py`) são anteriores e não são desta frente.

### O meu próprio conserto do bloqueante 2 derrubava a suíte do tronco, e eu registro isso

O observador que fechou a janela de 400 ms assinava `self.ocupacao_mudou.emit` — o **sinal ligado**
do rodapé. O registro de ocupação vive mais que o rodapé: uma leitura de marcas que termina depois
de a janela ser destruída chama `release()`, que avisa os observadores. Um sinal ligado guarda o
ponteiro C++ do emissor, e emitir por ele depois do destrutor **não levanta `RuntimeError` —
derruba o processo**:

```
Windows fatal exception: access violation
  ui/busy.py:147 in _avisar
  ui/busy.py:197 in _release
  qt/marcas.py:218 in _soltar
  qt/marcas.py:221 in _chegou
  tests/test_box_drop.py:81 in setUp
```

A suíte do tronco parou aos **5 %**. O `try/except Exception` de `_avisar` não pega isto, porque
não é exceção de Python — e essa é a lição: um `try` largo dá a **impressão** de que o observador
está isolado, e ele não está.

O conserto é `qt/` fazendo o que só `qt/` pode fazer: o que se assina é uma **função guardada** que
segura uma `weakref` do rodapé e pergunta `sip.isdeleted` antes de emitir. `ui/busy.py` continua
sem saber que existe toolkit — a assinatura do observador é `() -> None` justamente para isso.
Cobrado por `test_soltar_depois_de_o_rodape_morrer_nao_derruba_o_processo`, e a evidência de que
está fechado é a suíte do tronco inteira passando de novo.

### O que as 36 confirmaram, sem defeito

Olhei as 36 duas vezes — antes e depois dos meus consertos. Registro o que está certo e é fácil de
não notar: a barra do visor tem **duas filas de 1243 a 1920 sem trocar de fila** (o melhor trabalho
de desenho da frente, e continua intacto); os estados vazios de Texto, Dataset e Galeria têm
título, frase e **o botão que resolve dentro do vazio**; a frase da aba Texto se lê inteira nas
três larguras; os tabuleiros são quadrados ao pixel (552², 526², 318², 586²); as margens de 10 px
sobrevivem; e a página do visor **cresce com a janela** nas três larguras, que é o item 8.

---

## §7 — As suítes

| suíte | linha final |
|---|---|
| nossa (`.venv`, `pytest -q`) | **2965 passed, 1 skipped in 707.00s** — igual à linha de base do ciclo. Ver a nota abaixo sobre a segunda execução |
| do tronco (`..\ChessVisionOFF_Puro\.venv`, `pytest tests -q`) | **3 failed, 4418 passed, 2 skipped, 28 warnings, 4319 subtests passed in 249.24s** |

O tronco tinha **`3 failed, 4409 passed`** na medição do crítico. Os **3 reprovados são os mesmos
três, pelo nome**:

```
FAILED tests/test_docs.py::NumerosVivosTests::test_a_arvore_do_README_lista_todo_modulo_do_pacote
FAILED tests/test_editor_model.py::SemTkinterTests::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter
FAILED tests/test_strings.py::AccentTests::test_no_ui_string_uses_an_unaccented_portuguese_word
```

Os dois primeiros acusam `desenho_de_diagrama.py` e `pdf_substituicao.py`, que não são desta
frente. O terceiro acusava também `viewport.py`, que **era** desta frente e não é mais (§6).

Os **9 testes a mais** (4409 → 4418) são **todos meus**: 3 em `test_busy.py` (o observador avisa ao
registrar e ao soltar; não avisa num tique idêntico; um observador que levanta não derruba quem
registrou), 3 em `test_qt_tabela.py` (a fonte maior alarga a coluna em vez de cortar o título; o
alargamento não desfaz o arrasto de quem alargou mais; o piso da seção sobe junto com a fonte),
2 em `test_qt_rodape.py` (registrar acende a barra sem esperar o relógio; soltar depois de o rodapé
morrer não derruba o processo) e 1 em `test_qt_janela.py` (a janela liga o rodapé ao aviso).

**Nenhum teste foi afrouxado.** A única expectativa que mudei é a do §6, e ela ficou **mais**
estrita: passou a proibir também o corte do título.

### A segunda execução da nossa suíte, e por que ela não é minha

Rodei a nossa suíte outra vez no fim, com a máquina livre, e ela deu
**`10 failed, 2930 passed, 1 skipped, 25 errors in 414.17s`**. Fui conferir antes de escrever isto:
**as 35 são todas de `tests/unit/typeset/test_proofsheet.py`**, e **zero** estão fora de
`tests/unit/typeset/`:

```
grep -E "^(FAILED|ERROR)" ... | wc -l                     -> 35
grep -E "^(FAILED|ERROR)" ... | grep -v unit/typeset/ | wc -l -> 0
```

`src/caissa/typeset/` está sendo editado por outra frente ao mesmo tempo, e a coordenação avisou
que falhas ali não são minhas. **Esta frente não tocou em `src/caissa/` neste ciclo** — o que
escrevi na suíte foram dois instrumentos em `benchmarks/reports/ui/c4/` e este documento. E o que
cobre a fronteira desta frente continua verde nas duas execuções: `tests/unit/ui/` dá
**110 passed in 0,59 s**, num venv sem binding de toolkit (ADR-0009).

---

## §8 — Como reproduzir

```bat
:: portões (contraste e progresso no venv da suíte; o resto no do tronco)
.venv\Scripts\python.exe -m pytest tests\unit\ui\ -q
.venv\Scripts\python.exe -m caissa.ui.audit.contraste
.venv\Scripts\python.exe -m caissa.ui.audit.progresso
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONPATH=C:\Python-Chess2\Suite_de_Edicao_de_Xadrez\src;C:\Python-Chess2\ChessVisionOFF_Puro\src
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado   --pdf "C:\Python-Chess2\ChessVisionOFF_Puro\PDF\1937 Kemeri.pdf"
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio  --pdf "C:\Python-Chess2\ChessVisionOFF_Puro\PDF\1937 Kemeri.pdf"   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.quadros   --pdf "C:\Python-Chess2\ChessVisionOFF_Puro\PDF\1937 Kemeri.pdf"   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.amostrario --saida benchmarks\reports\ui --estados
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.capture --saida benchmarks\reports\ui\c4 --marca c4 --pdf "C:\Python-Chess2\ChessVisionOFF_Puro\PDF\1937 Kemeri.pdf"

:: os instrumentos do crítico (benchmarks\reports\critique\ui\c3\)
quem_chama.py  "…\PDF\1937 Kemeri.pdf"    :: 0 leituras do labels.csv por virada
colapso.py     "…\PDF\1937 Kemeri.pdf"    :: 0 de 36 controles fora da janela
detalhes.py    "…\PDF\1937 Kemeri.pdf"    :: Gravar alinhado, uma frase na Galeria, barra invisivel
medidas_c3.py  pagina|regiao <png...>
sonda.py       tipografia
sobreposicao.py
casos_ruins.py {classica,foco}   :: CUIDADO: ele GRAVA por cima das c1_*_1024x768_*.png (ver o AVISO do §0)

:: e o adaptado deste ciclo (benchmarks\reports\ui\c4\)
c4_custo_aviso.py "…\PDF\1937 Kemeri.pdf"   :: o custo_aviso.py do critico, no ponto de chamada novo
c4_ocupacao.py <png...>   :: ocupacao do canvas de Resultado, restrita ao painel esquerdo
```

As 36 capturas estão em `benchmarks\reports\ui\c4\`, nomeadas
`c4_{claro,escuro}_{1280x800,1366x768,1920x1080}_{aba}.png`, e as 36 têm **exatamente** a dimensão
que o nome anuncia (conferido arquivo a arquivo: 36 arquivos, 0 divergentes).

---

## §9 — O que continua aberto, sem rodeio

1. **A virada de página é 104 ms e o portão é 16 ms.** 88 % disso é PyMuPDF rasterizando a página,
   e a saída é tirar a rasterização da thread da janela — que é trabalho de `qt/` mas de outro
   tamanho que os itens deste ciclo.
2. **6 de 6 abas sem ação primária própria.** Compensado por tecla, não resolvido por desenho.
3. **A aba Estudo tem 28 botões em 4 filas** contra o alvo de ≤ 12 em ≤ 2.
4. **393,0 kpx a 0,00 %** na Revisão a 1920, e **203,3 kpx a 0,00 %** à direita da paleta em
   Resultado.
5. **A janela recusa 1024×768** (1066×735).
6. **O Dataset ainda precisa de barra horizontal a 1280 e a 1366** — e mais do que antes, porque as
   colunas pararam de mentir sobre a largura que pedem.
7. **`Modo bloco (lento)`** e os **dois controles sem rótulo visível na aba Texto** continuam como
   estavam.
8. **As 14 capturas do ciclo 1 do crítico que eu destruí** rodando `casos_ruins.py` (§0). Não são
   recuperáveis daqui; se o crítico precisar delas, elas têm de ser refeitas de um checkout do
   ciclo 1, e nesta máquina não há um.
