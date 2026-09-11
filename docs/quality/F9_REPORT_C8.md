# F9 — Interface, relatório do ciclo 8

Responde ao `docs/quality/F9_CRITIQUE_C7.md`. Todo número abaixo saiu de um comando rodado nesta
sessão; onde um número piorou, ele está aqui com o mesmo destaque dos que melhoraram.

**O bloqueante era um: o estado vazio da aba que o produto abre mandava apertar um nome que a pele
padrão desenhava em zero controles.** Ele está fechado nas duas metades que o crítico exigiu — o
produto desenha o nome, e o portão deixou de aceitar dica —, com a prova de vida que ele pediu e
que **reprova** com a régua do ciclo 7.

**Achei um oitavo instrumento cego, e ele é do arnês desta frente**: as 36 capturas dependiam do
`sash_fraction` guardado em `data/app_tkinter_state.json`, que **toda** janela aberta e fechada
reescreve. Medido: o divisor foi de x=980 (ciclo 6) para x=875 numa recaptura desta sessão **sem
uma linha de leiaute mudar**, e com ele os itens 6, 7 e 8 — os três que falam do painel. As
primeiras medidas que escrevi neste relatório diziam *"ocupação subiu de 73,6 % para 82,9 %"*, e
era o artefato. Está consertado em `capture.py` e o número honesto está no §6.

---

## Resumo

| # | item | número medido | veredito |
|---|---|---|---|
| **1 (bloqueante)** | o nome citado no estado vazio está **desenhado** | `c7_vazio_na_tela.py` do crítico: **30 de 30 linhas `DESENHADO=sim`** (era 27/30) | **FECHADO**, com prova de vida nos dois sentidos |
| 2 | portão de progresso decidia "total conhecido" pelo **nome da variável** | 5 nomes diferentes, **1 veredito**; e `determinado` passa a ser a **faixa medida** do widget | **FECHADO** |
| 3 | teste da FEN montava o caso cortado e via só de que lado | **48 medições, 0 cortes silenciosos**; a marca é medida no `grab()` | **FECHADO** |
| 4 | detector de thread: 7 de 8 formas do crítico escapavam | **8 de 8** (crítico) e **8 de 8** na minha sabotagem nova; 3 controles negativos mudos | **FECHADO** |
| 5 | rodapé elidia 39 de 62 chars com 1534 px livres | **0 rótulos elididos** a 1920, 1366 e 1280 | **FECHADO** |
| 6 | item 4 com o escopo da janela: 11 glifos de texto | **0 glifos**; 18 botões só-de-ícone, caixa única **16×16**, amplitude **0 px** | caixa **FECHADA**, tinta **ABERTA** (17,6 %–41,4 %) |
| 7 | atribuição do portão de bloqueio | as **sete** operações têm atribuição, e cada uma publica a **cobertura** | **FECHADO** o instrumento; a E/S de disco fica **ABERTA** com número |
| 8 | dois `Cancelar` visíveis com estados divergentes | **3 → 2**; os 2 que ficam são a duplicação da pele Foco | **PARCIAL** |
| 9 | aspas retas nos três estados vazios | 3 de 3 com aspas tipográficas | **FECHADO** (com uma nota sobre o instrumento do crítico) |
| 10 | janela não desce de 1066×735 | inalterado; declarado com número no §9 | **ABERTO, declarado** |

---

## Item 1 — o bloqueante. **FECHADO**

### O que estava errado

`qt/painel_de_resultado.MENSAGEM_VAZIA` manda usar **"OCR todos diagramas"**. Na pele **clássica**,
que é a padrão, esse nome era desenhado por **zero** controles visíveis nas três larguras; o que o
olho achava a 40 px, em azul, era `OCR melhor diagrama` — **outro comando**. O nome existia só na
**dica** do botão só-de-ícone, e a guarda escrita no ciclo 6 para pegar exatamente isso
(`EstadoVazioNaTelaTests._lido_na_tela`) **aceitava `toolTip()` como "na tela"**.

### O conserto de produto: o botão desenha o nome que a pele corrente não desenha

`qt/painel_do_pdf.PainelDoPdf.nomear_o_que_o_cromo_nao_desenha(cromo)` recebe o **contêiner do
cromo** e lê dele o `text()` do que a fila ou a fita acabaram de montar. Onde o cromo não escreve o
nome, a barra do visor escreve; onde escreve, o botão fica só com o ícone.

* A regra de **quais** botões entram é `_e_outro_nome`, a mesma da dica do ciclo 6: só o botão cujo
  nome de botão é um **nome diferente** do rótulo por extenso — não um glifo (`+`, `-`), não um
  encurtamento (`"Tirar a caixa"` de `"Tirar a caixa do diagrama selecionado"`). Hoje o catálogo tem
  exatamente um caso, `ler_pagina`; a regra está escrita para o próximo.
* **O que entra na comparação é medido, não declarado.** Uma tabela "quais nomes cada pele mostra"
  divergiria do cromo no dia em que alguém tirasse um comando do destaque — que é a forma exata do
  defeito que este conserto fecha.
* **O espaço em branco é normalizado**, e isso saiu de medir: a fita quebra o rótulo em duas linhas
  (`"OCR todos\ndiagramas"`), e comparar o literal fazia a barra escrever o nome uma **segunda vez**
  na pele fita. Sem isso o conserto fecharia um item abrindo outro.

Medido, `benchmarks/reports/ui/c8/c8_barra_do_visor.py`, três peles × sete larguras:

```
  classica  1920..1243  filas=1   ler_pagina: texto='OCR todos diagramas'  controles_visiveis_com_o_nome=1
  classica  1066        filas=2   ler_pagina: texto='OCR todos diagramas'  controles_visiveis_com_o_nome=1
  foco      1920..1066  filas=1   ler_pagina: texto=''                     controles_visiveis_com_o_nome=1
  fita      1920..1243  filas=2   ler_pagina: texto=''                     (a fita escreve o nome)
```

**Nunca dois, nunca zero.** A barra do livro continua em **uma fila de 1243 a 1920** — o alvo do
ciclo 6 —, e cai para duas a **1066**, que é o piso da janela e está abaixo do alvo declarado
(1366). O custo em pixel: o `minimumSizeHint` da barra vai de **290 para 404 px**.

### O conserto de portão: `toolTip()` não é a tela

`tests/test_qt_janela.EstadoVazioNaTelaTests._lido_na_tela` lê **só o `text()`** de um controle
visível. Além disso:

* o portão passou a rodar em **todas as peles registradas** (3, e não 2) e nas **três larguras** que
  o arnês captura, porque um nome pode caber a 1920 e sumir a 1280;
* a regex de citação aceita **os dois pares de aspas** — ver o item 9, e a razão é que trocar aspas
  não pode *apagar* a cobrança em vez de a manter.

### A prova de vida, e ela reprova com a régua do ciclo 7

`test_apagar_o_texto_do_botao_reprova_este_portao` repõe o estado do ciclo 7 **pelo caminho do
próprio produto** — mente que o cromo já desenha o nome, o que apaga o texto do botão **e** repõe a
dica de dois nomes — e exige que o portão acuse. Rodado nos dois sentidos:

```
  regua de hoje (so text())        : 3 passed, 3 subtests passed
  regua do ciclo 7 (aceita toolTip): 2 failed  -- test_apagar_o_texto_do_botao_reprova_este_portao
                                                  test_a_varredura_le_o_texto_desenhado_e_nao_a_dica
```

**Sabotar só com `setText("")` seria uma sabotagem mais fraca** — ela também apagaria o nome da
dica, e o portão reprovaria mesmo com a régua velha, provando nada sobre a régua.

### O alvo do crítico, com o instrumento dele

```
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe benchmarks\reports\critique\ui\c7\c7_vazio_na_tela.py
  -> 30 linhas, 30 DESENHADO=sim, 0 DESENHADO=NAO      (antes: 27 sim / 3 NAO)
```

*(As 30 linhas são 2 peles × 3 larguras × 5 nomes citados. O crítico escreveu "18 linhas"
esperando 3 mensagens; as três mensagens citam **cinco** nomes.)*

**Uma ressalva de instrumento, e ela é importante para quem for reler:** o item 9 troca as aspas
retas por tipográficas, e a regex do `c7_vazio_na_tela.py` é `r'"([^"]{3,60})"'` — rodado contra as
frases de hoje ele acha **zero** citações e não imprime linha nenhuma, que **não** é "passou", é
"não mediu". Por isso `benchmarks/reports/ui/c8/c8_vazio_na_tela.py` é o arquivo dele com **uma**
linha alterada (a regex aceita os dois pares), e é ele que devolve as 30 linhas acima.

---

## Item 2 — o portão de progresso decidia pelo nome de uma variável. **FECHADO**

### O furo, reproduzido

`caissa.ui.audit.progresso` marcava "total conhecido" procurando
`("total","count","epochs","epocas","paginas","n_","len")` **no texto do `detail=`**:

```
  detalhe='f"{quantas} amostra(s)"'  -> 0 defeitos
  detalhe='f"{total} amostra(s)"'    -> DEFEITO BLOQUEANTE
```

### Metade 1: a heurística não olha mais nome de variável

`PISTAS_DE_TOTAL` **saiu**. No lugar, duas regras estruturais:

* `_e_contagem` — a expressão interpolada é uma chamada a um contador embutido
  (`len(...)`, `sum(...)`, …). Quem decide é a **função chamada**, não a palavra.
* `_numero_calculado_na_mesma_funcao` — o nome interpolado é atribuído, **na mesma função**, ao
  resultado de uma **chamada**, e o `register(...)` daquela função não recebe `total=`. É o
  `quantas = self.contagem_de_amostras()` a duas linhas do `register`.

Prova de vida (`tests/unit/ui/test_medicao.py`, parametrizado):

```
  nome da variavel: quantas | total | n | xyz | count   ->  os cinco: total_conhecido=True, bloqueia()
  evidencia: "a propria funcao calcula o numero: quantas = self.contagem_de_amostras()
              -- e o detail o imprime sem que `total=` o receba"
```

E o outro lado, para o portão não passar a gritar: `detail=f"motor {motor}"` com
`motor = self._motor` (um atributo **lido**, não um número calculado) **não** acusa — é o único
`detail=` interpolado do tronco que a regra tem de deixar em paz, e ela deixa.

### Metade 2: "determinada" passa a ser a **faixa medida** do widget

`qt/rodape.RodapeDaJanela.barra_de_progresso()` é novo, e
`caissa.ui.audit.progresso.faixa_da_barra_do_rodape(total)` constrói o rodapé de verdade, entrega
uma `BusyOperation` com aquele `total` e lê `minimum()`/`maximum()`. O relatório passa a publicar:

```
  leitura do dataset      faixa medida no rodape vivo: min=0 max=0   -> INDETERMINADA
  treino do modelo        faixa medida no rodape vivo: min=0 max=100 -> DETERMINADA
  exportação para PGN     faixa medida no rodape vivo: min=0 max=100 -> DETERMINADA
  ...
```

Sem binding do Qt (a **nossa** venv não tem PyQt6) a coluna volta a ser lida do código e a
evidência **diz isso**: `"faixa NAO medida (sem binding do Qt): lida do argumento total="`.

**Um teste derrubou a primeira forma desta mudança, e o defeito era meu**: eu tinha ligado
`total_conhecido` a `determinado`, e com o rodapé sabotado para nunca sair de `(0,0)` uma operação
que passa `total=289` ficava com `total_conhecido=False` — ou seja, **quebrar a barra apagava o
defeito de quebrar a barra**. Hoje `passa_total` é prova independente, e
`test_a_coluna_determinada_e_a_faixa_do_widget_e_nao_o_argumento` sabota o rodapé nos dois sentidos.

### O produto: a leitura do dataset parou de anunciar um total que a barra não honra

Com as duas metades, o portão acusou `leitura do dataset` — **total=sim, determinada=NÃO** — que é
o defeito da carta §3.3. O `detail` era `f"{quantas} amostra(s)"` = **"5431 amostra(s)"** ao lado de
uma marquise de 59 px que anda e dá a volta, em 28 das 36 capturas.

**O que fiz, e o que não fiz.** O `detail` passa a ser o arquivo que está sendo lido —
`labels.csv`, a mesma escolha de `qt/exportador.py` —, e a contagem continua na tela onde ela não é
denominador de nada: o rótulo da aba, `Dataset (5.431)`. Portão limpo:

```
  leitura do dataset      NAO   NAO   sim   src/chess_diagram_ocr/qt/painel_do_dataset.py:461
  Nenhum defeito bloqueante de progresso.
```

**A barra continua indeterminada, e digo por quê sem atenuar.** Quem lê as linhas é
`dataset_browser.load_rows` → `labels.LabelStore._load_rows`, e **nenhum dos dois aceita callback de
progresso**: não há argumento por onde passá-la. Uma barra determinada com um `feito` que ninguém
pode incrementar fica parada em 0 % do começo ao fim, que é pior — parece travada. O conserto de
verdade é uma linha no laço `for entry in entries` de `dataset_browser.load_rows`, e
`chess_diagram_ocr/dataset_browser.py` está **fora** do que esta frente pode escrever (a ordem de
serviço dá `ui/` e `qt/`). Fica registrado com o arquivo e o laço nomeados.

---

## Item 3 — o teste da FEN montava o caso cortado e via só de que lado. **FECHADO**

O teste do ciclo 6 afirma `cursorPositionAt(QPoint(4, h/2)) == 0` **três linhas depois de
assegurar** que o campo é estreito demais. Ele não tinha como reprovar enquanto a ponta **direita**
sumisse em silêncio — e ela sumia: 3 a 33 caracteres a 1366, 1280 e 1024.

**Produto:** `qt/rotulo.CampoQueAvisaQueContinua`, um `QLineEdit` que **desenha** uma reticência na
margem direita quando o texto não cabe. O `text()` continua inteiro — elidir o texto de um campo
editável corromperia o que `apply_fen` lê e gravaria a FEN elidida como se fosse a posição. A marca
some quando não é necessária: aviso permanente é ruído, e ruído permanente se aprende a não ver.
Usado nos **dois** campos de FEN da janela (Estudo e Resultado).

**Régua:** `benchmarks/reports/ui/c8/c8_fen_avisa.py` conta **tinta na faixa da marca**, no
`grab()`, e não o estado interno do widget — um campo que ligasse a marca sem desenhá-la passaria
numa asserção sobre `textMargins()`, e essa é a forma de cegueira deste ciclo.

```
  2 peles × 2 campos × 4 larguras × 3 FENs = 48 linhas; 0 com corte silencioso (alvo 0)
  1024 [Estudo] meio-jogo (72): campo=286 px pede=504 px corta=33 chars
                                faixa_da_marca=13 px  tinta_na_faixa=14 px  AVISA
  1920 [Estudo] meio-jogo (72): campo=535 px pede=504 px corta= 0 chars
                                faixa_da_marca= 0 px  tinta_na_faixa= 0 px  sem marca
```

**Prova de vida**, sabotando `_reavaliar` para nunca acender a marca:

```
  com a marca : 6 passed, 4 subtests passed
  sem a marca : 4 failed  (largura=720, 560, 460, 380)
                e o teste do ciclo 6 (`mostra_o_comeco`) continua PASSANDO -- era ele o cego
```

---

## Item 4 — o detector de thread. **8 de 8 do crítico, 8 de 8 da minha**

### As oito do crítico do ciclo 7 (7 escapavam)

```
  a  apelido por atribuicao  Fabrica = threading.Thread    -> INVISIVEL (constroi Fabrica)
  b  functools.partial(threading.Thread, ...)              -> INVISIVEL (embrulha threading.Thread em partial)
  c  self._pool.map(fn, itens)                             -> INVISIVEL (submete por self._pool.map)
  d  asyncio.to_thread(...)                                -> INVISIVEL (submete por asyncio.to_thread)
  e  trabalhador.moveToThread(self._fio)                   -> INVISIVEL (submete por trabalhador.moveToThread)
  f  subprocess.Popen([...])                               -> INVISIVEL (constroi subprocess.Popen)
  g  QProcess(...).start(prog, args)                       -> INVISIVEL (constroi QProcess)
  h  importlib.import_module("threading").Thread(...)       -> INVISIVEL (constroi mod.Thread)
```

**Cada uma no nome da função que a abre**, que era a segunda metade da queixa: antes, `c` e `e`
apareciam só pela construção que o `__init__` fazia, e *"uma linha dizendo `__init__ constroi
QThread` não diz que `e_move_to_thread` é uma operação de fundo"*.

### As oito minhas (`benchmarks/reports/ui/c8/sab_c8/`) — sete escapavam

```
  a  self.FABRICAS["fundo"](...)          (a classe num dicionario)   -> era invisivel ao portao
  b  multiprocessing.pool.ThreadPool(4)   (o termo final nao e Pool)  -> era invisivel
  c  asyncio.create_task(...)                                          -> era invisivel
  d  asyncio.run_coroutine_threadsafe(...)                             -> era invisivel
  e  QThreadPool.globalInstance().tryStart(...)                        -> era invisivel
  f  self.FABRICA(...)  (apelido em atributo de classe)                -> ja era pego
  g  os.startfile("relatorio.pdf")                                     -> era invisivel
  h  getattr(threading, "Thread")(...)                                 -> era invisivel
```

Depois do alargamento: **DEFEITOS BLOQUEANTES (8)**, um por método.

### Os três controles negativos, que também são medida

`n1_relogio_da_interface` (`self._relogio.start(250)`), `n2_map_comum`
(`list(map(str, range(10)))`) e `n3_partial_comum` (`partial(self._ir, 1)`) **não** aparecem. É por
isso que `map` não entrou em `METODOS_DE_SUBMISSAO` e sim em `METODOS_DE_POOL`, onde ele exige um
receptor com nome de pool; e `partial` só conta com classe de thread no primeiro argumento —
`qt/painel_da_galeria.py` tem dez `partial(self._ir, …)` que não podem acusar.

### As catracas anteriores e o tronco real

```
  sabotagem do critico do ciclo 5 : DEFEITOS BLOQUEANTES (6)   -- 6 de 6, cópia intocada
  sabotagem do critico do ciclo 7 : DEFEITOS BLOQUEANTES (10)  -- as 8 formas + 2 do __init__
  sabotagem C8 (minha)            : DEFEITOS BLOQUEANTES (8)   -- 8 de 8, 3 controles mudos
  TRONCO REAL                     : 13 operacoes de fundo em qt/, 0 invisiveis
```

A régua gêmea de `tronco/tests/test_busy.py` recebeu **as mesmas** mudanças, e a `SABOTAGEM_C8`
ficou lá ao lado da C5 e da C6, com os dois testes (as oito formas, e os três controles negativos).
Era o ponto cego que o crítico do ciclo 5 nomeou: *"o teste e o portão compartilham a régua"* — eles
compartilham, e por isso mudam juntos.

---

## Item 5 — o rodapé. **FECHADO**

`RotuloElidido` ganhou `largura_desejada`, e o rodapé passa `0` = "peça o texto inteiro". O teto de
130 px é **da barra do visor**, onde ele impede um nome de livro de 149 caracteres de decidir o
refluxo; no rodapé, que é uma linha só, ele só produzia reticência gratuita. O `minimumSizeHint`
continua **zero**, então o defeito nº 2 da crítica do ciclo 1 (o nome do arquivo decidindo a menor
tela em que o programa cabe) não volta.

`c7_rodape_elisao.py` do crítico, sem alteração:

```
  === janela 1920 ===  RotuloElidido  dado= 313 px  tinta= 313 px  inteiro pede 313 px   (sem ELIDE)
  === janela 1366 ===  RotuloElidido  dado= 313 px  tinta= 313 px  inteiro pede 313 px   (sem ELIDE)
  === janela 1280 ===  RotuloElidido  dado= 313 px  tinta= 313 px  inteiro pede 313 px   (sem ELIDE)
```

Antes: `dado=130 px, inteiro pede 313 px, ELIDE`, com **39 de 62 caracteres perdidos** e 1534 px
livres. `minimumSizeHint` da janela: **1066×735**, inalterado.

**Portão novo, em `tests/test_qt_rodape.DocumentoTests`**, com a régua que o crítico prescreveu —
comparar `texto_inteiro` com `text()` **e somar a folga da barra**:

```
  test_nenhum_rotulo_elide_enquanto_ha_folga_na_mesma_faixa   (1920, 1366, 1280)
  test_sem_folga_ele_volta_a_elidir                            (320 px: tem de elidir)
  test_o_rotulo_do_documento_continua_sem_decidir_a_largura_minima  (minimumSizeHint == 0)
```

Prova de vida (devolvendo o teto de 130 px ao rodapé): **4 failed**, as três larguras mais o teste
do `sizeHint`.

**Um detalhe que só apareceu ao escrever o teste**, e vale para quem escrever o próximo: um
`QWidget` escondido guarda o `QResizeEvent` em `WA_PendingResizeEvent` e só o entrega quando
aparece — sem `show()`, `RotuloElidido.resizeEvent` nunca corre e o teste mede a ausência de
leiaute, não a régua.

---

## Item 6 — os ícones, com o escopo da janela. **Caixa fechada, tinta aberta**

A varredura do ciclo 6 era `j.pdf.findChildren` — o painel do visualizador e mais nada. Na janela
inteira sobravam **onze** caracteres de texto fazendo papel de ícone, com caixas de tinta de
**5×3 a 9×12 px**, e o par `◀`/`▶` diferindo em **2,4× de massa**.

Hoje, `c7_icones_da_janela.py` do crítico, sem alteração:

```
  GLIFOS DE TEXTO fazendo papel de icone: 0      (era 11)
```

E a régua com o escopo certo e as famílias separadas
(`benchmarks/reports/ui/c8/c8_icones_da_janela.py`):

```
  botoes so-de-icone: 18
  caixas distintas  : [(16, 16)]
  amplitude da caixa: 0 px de largura, 0 px de altura   (alvo <= 1)
  tinta/caixa       : 17.6 % a 41.4 %  -> amplitude relativa 80.8 %   (alvo <= 20 %)
```

**A tinta continua aberta e não vou dizer que não está.** 80,8 % contra o alvo de 20 %. O extremo
baixo são as setas de "um item para trás/adiante" (17,6 %–18,0 %), que são **abertas** — um V de
traço — e o alto é `ajustar_pagina` (41,4 %), que é fechado. Fechar isso é redesenhar glifo, e a
espessura do traço é declarada uma vez para a família inteira (`ui/icones.TRACO_RELATIVO`), de
propósito.

**O que mudou, arquivo a arquivo.** Dois desenhos novos (`inicio_da_linha`, `fim_da_linha` — a barra
**é** a informação: `|◀` é "primeiro"); quatro comandos da Estudo ganharam `icone=`, dois deles
**compartilhando** o desenho de `diagrama_anterior`/`proximo_diagrama` (é a mesma seta e o mesmo
gesto; uma segunda cópia dos mesmos três pontos seria a mesma decisão declarada duas vezes); e um
ajudante compartilhado, `qt/icones.vestir`, que põe o desenho **e apaga o glifo** — um botão com
ícone e glifo desenha os dois lado a lado.

**As setas de diagrama entraram na grade única, e isso mudou uma decisão declarada.** Elas eram
32×64 — estreitas e altas de propósito, para se distinguirem das setas de **página**, que são 60×60
— e `na_grade` enche o lado maior, então elas saíam com caixa de tinta de **8×16** ao lado de irmãs
de 16×16. Hoje são ~60×60 e o que separa as duas famílias é o **preenchimento**: as de item são
abertas (V), as de página são triângulos cheios. Preenchimento lê-se a 16 px; proporção de 2:1
contra 1:1 não.

---

## Item 7 — a atribuição do portão de bloqueio. **Instrumento fechado; a E/S de disco aberta, com número**

Três coisas erradas, e as três estão consertadas em `caissa.ui.audit.bloqueio`:

**(a) `relatorio["operacoes"][:4]`** — com sete violações, três ficavam sem atribuição no relatório
de texto, que é o único que se lê. Hoje **todas as que violam** têm bloco de atribuição.

**(b) A passada de perfil rodava na janela quente.** Ela vinha depois das três execuções medidas —
com o PDF aberto, a aba Dataset já mostrada e o CSV já lido —, e o `method.por_que_o_pior` do
próprio relatório diz que **só a execução 1 é fria**. Hoje `_perfilar` monta uma **janela nova**, e
o escoamento da fila de eventos entra no perfil (é o que `medindo` cronometra: a pilha do pior da
aba Dataset aponta para `bloqueio.py:667 escoar`, e o perfil não o via).

**(c) A cobertura passou a ser publicada.** É a linha mais importante do bloco:

```
  ANTES (medido pelo critico):  aba Dataset -> o perfil reproduzia 1,05-1,41 ms de 74,5 ms (1,9 %)
  DEPOIS (uma execucao, --execucoes 1):
    204 ms -- abrir PDF          COBERTURA: 210.5 ms de 203.8 ms (103.3 %)
     95 ms -- pagina 121         COBERTURA:  89.7 ms de  95.1 ms ( 94.4 %)
     93 ms -- aba Dataset        COBERTURA: 111.0 ms de  93.3 ms (119.0 %)
     93 ms -- pagina 41          COBERTURA: 105.3 ms de  92.5 ms (113.8 %)
     86 ms -- pagina 42          COBERTURA:  96.5 ms de  85.6 ms (112.8 %)
     61 ms -- rasterizar         COBERTURA:  64.8 ms de  61.3 ms (105.7 %)
     22 ms -- aba Galeria        COBERTURA:  34.2 ms de  22.3 ms (153.6 %)
```

Abaixo de `COBERTURA_MINIMA = 50 %` o relatório escreve `<<< o perfil NAO reproduz o congelamento`
ao lado do número. Sem essa linha, quem lê não tem como saber que as porcentagens publicadas são as
de 1,4 ms e não as do congelamento — e foi assim que *"o resto é PyMuPDF"* cobriu 4 de 7 e errou na
maior.

### O que a atribuição honesta diz

**`abrir PDF`, o pior (203,8 ms):**

```
  93.2 ms  44.3 %  builtins (C)          <- escoamento da fila de eventos + PyMuPDF via C
  82.5 ms  39.2 %  PyMuPDF
  26.8 ms  12.7 %  pathlib/os (disco)
   3.1 ms   1.5 %  qt/ (esta frente)
  as funcoes:
    67.6 ms  fz_run_display_list                        <- painel_do_pdf.py:775 desenhar_pagina
    41.7 ms  sqlite3.Connection.execute                 <- janela.py:1786 _atualizar_abas
    14.5 ms  nt.stat                                    <- marcas.py:77 _marca_de
     9.2 ms  pathlib._select_from                       <- escolha_de_bases.py:48 _mesmo_conjunto
```

**A E/S de disco e de banco na thread da janela é real e é desta frente**, e o número exato, numa
passada isolada (`cProfile` sobre `abrir_pdf` só):

```
  31 chamadas de nt.stat                 = 17.1 ms
   7 chamadas de sqlite3 execute         = 13.6 ms
  painel_da_galeria.py:1087 _abrir_cache_de_posicoes, 1 chamada, cumtime = 23.0 ms
```

`load_pdf` da Galeria abre o cache de posições (SQLite) **na thread da janela**, e isso é 23 ms dos
204. **Não consertei**, e digo por quê: `_abrir_cache_de_posicoes` também alimenta
`model.position_cache`, que é o que decide o rótulo e o estado do botão "Partidas da base"
imediatamente depois; adiar isso corretamente é mudar `ui/gallery_model.py` para abrir o cache sob
demanda, e não cabia neste ciclo ao lado do bloqueante. Fica com arquivo, linha e número.

**`aba Dataset`, o congelamento que não estava em perfil nenhum:** com a janela fria e o escoamento
dentro, o perfil reproduz **111,0 ms de um pior de 93,3 ms** e diz o que é —
**96,4 % `builtins (C)`, 102,6 ms de `processEvents` sem chamador Python**. Ou seja: o que trava a
janela ao clicar na aba Dataset é o **Qt montando e pintando a aba pela primeira vez**, não PyMuPDF
(0,0 % ali) e não `qt/` (1,5 %). Essa é a explicação que o crítico pediu, e ela reproduz o evento.

---

## Item 8 — um rótulo, um controle. **3 → 2**

`c7_rotulos_repetidos.py` do crítico, sem alteração:

```
  ANTES                                              DEPOIS
  [Galeria]  'Cancelar' 2x  1 ligado / 1 cinza  <<<  0 rotulos repetidos
  [Revisão]  'Cancelar' 2x  0 ligado / 2 cinza       0 rotulos repetidos
  [Resultado, pele foco] 'Aplicar a FEN digitada' 2x  1/1  <<<  (continua)
  [Resultado, pele foco] 'Salvar a posição'       2x  1/1  <<<  (continua)
  [Texto]   'Ler folha'      2x  2 ligados            (continua, e é o padrão do estado vazio)
  [Galeria] 'Varrer o livro' 2x  2 ligados            (continua, idem)
```

Os dois `Cancelar` dos painéis passaram a dizer **o que** cancelam (`Cancelar a varredura`); o do
rodapé é o genérico — ele vale para toda operação registrada — e fica como está.

**Os dois que ficam com estados divergentes são a pele Foco duplicando ações do painel na fila de
pílulas**, e fechá-los é sincronizar o estado de habilitação entre a fila e o painel — o que exige
que cada painel publique a habilitação de cada comando. Fica aberto, com o número.

`'Ler folha'` e `'Varrer o livro'` aparecem duas vezes **com o mesmo estado**, e as duas são "o
botão da barra mais o botão dentro do estado vazio" — o padrão que o item 14 do §7 do ciclo 2
introduziu de propósito (título, frase e **o botão que resolve**, dentro do vazio que ele preenche).

---

## Item 9 — aspas tipográficas, e o instrumento que elas cegam

As três mensagens de estado vazio usam `ui/strings.ASPA_ABRE`/`ASPA_FECHA` (`“”`):

```
  Use “Ler folha” para transcrever a página aberta no visualizador, ou “Achar no texto…” …
  Nenhuma folha lida. Use “Ler folha” … ou “Achar no texto…” …
  Nenhum diagrama aberto. Clique num diagrama marcado da página, ou use “OCR todos diagramas” …
```

**E aqui há uma armadilha que este ciclo inteiro é sobre não cair:** uma régua que procure `"` reto
numa frase de aspa curva devolve **zero citações** e passa em verde por não ter o que cobrar. Por
isso o portão (`EstadoVazioNaTelaTests`) aceita **os dois pares**, e por isso
`benchmarks/reports/ui/c8/c8_vazio_na_tela.py` existe: é o `c7_vazio_na_tela.py` do crítico com a
regex alargada, e é ele que devolve as 30 linhas do item 1. **Rodado como está, o do crítico não
imprime nada.**

Também nesta linha: `Limpar os headers` → **`Limpar os cabeçalhos`** e `Copiar headers para todos`
→ **`Copiar cabeçalhos para todos`** (as oito *tags* `White`, `Black`, … ficam em inglês: são o
formato do arquivo, e traduzi-las gravaria um PGN que nenhum outro programa lê); e os dois campos
empilhados sob `outro` ganharam dica de conteúdo — **`nome do cabeçalho`** e **`valor`** —, porque
medido na captura era o contrário do que o comentário do código dizia: quem ouve recebia a
distinção (`accessibleName`) e quem vê, não.

---

## O oitavo instrumento cego, e ele era do arnês desta frente

As 36 capturas passavam pelo `sash_fraction` guardado em `data/app_tkinter_state.json`, e **toda**
janela aberta e fechada por qualquer instrumento reescreve esse arquivo ao sair. Medido nesta
sessão, sem uma linha de leiaute mudar:

```
  fracao guardada 0,5625 (ciclo 6)  -> painel da Revisão 1050 px, divisor x=980
  fracao guardada 0,3755 (agora)    -> painel da Revisão  945 px, divisor x=875
```

**Todo número que fala do painel depende disso** — item 6 (vazio de painel), item 7 (ocupação) e
item 8 (largura da coluna "Motivo"). Com a fração drifteada eu quase publiquei *"a ocupação subiu de
73,6 % para 82,9 % e o poço morto caiu de 109,7 para 37,3 kpx"*: os dois números eram verdadeiros e
não queriam dizer nada — o painel é que estava 105 px mais estreito.

**Conserto**, em `caissa.ui.audit.capture`: a captura passa a usar **estado próprio**
(`capture_estado.json`, ao lado das imagens) e a fixar o divisor em `FRACAO_DO_DIVISOR = 0,566`,
que é a fração que reproduz o painel de 1050 px com que o ciclo 6 mediu. Refixado **a cada largura**,
porque o `QSplitter` reparte o que sobra pelos fatores de esticamento (2:3) e a mesma fração dá
divisores diferentes conforme a janela cresce.

Com isso os itens 6 e 7 voltam a ser comparáveis:

| | ciclo 6 | ciclo 8 (mesma moldura) |
|---|---|---|
| item 7, ocupação clara | 73,6 % | **73,1 %** |
| item 7, ocupação escura | 70,2 % | **69,7 %** |
| item 7, à direita da paleta (clara) | 109,7 kpx | **114,5 kpx** |
| item 6, painéis > 200 kpx a 1920 | 10 de 12 | **10 de 12** |
| item 6, a 1366 e a 1280 | 0 de 24 | **0 de 24** |

Os dois pioraram de fração de ponto, e a causa é a mesma: a paleta ficou um pouco mais larga porque
o `✕` virou desenho de 26 px. **Itens 6 e 7 continuam abertos.**

---

## Os portões, todos rodados

| portão | resultado |
|---|---|
| Contraste WCAG AA | **296 pares / 218 sob portão / 0 reprovados** nas duas peles; menor folga 3,27:1 e 3,03:1. **PASSOU** |
| Teclado + nome + papel | 24+52+30+39+21+50 = **216 focáveis**, 0 sem nome, 0 sem papel, ciclo fecha nas seis abas. **PASSOU** |
| Progresso | **8 indicadores, 13 operações de fundo, 0 invisíveis, 0 defeitos bloqueantes**; faixa da barra **medida** no rodapé vivo |
| Rodapé (barra × Cancelar) | **8 ociosas / 28 ocupadas / 0 contradições**, face do Cancelar separada nas duas peles |
| Sobreposição / fora | `minimumSize` **1066×735**; **0** controles fora em 1024×768, 900×700 e 800×600 |
| Nada bloqueia > 16 ms | **REPROVOU nas três execuções, 7 operações**. Piores, medianas de 3: abrir PDF **238,2 ms**, p.121 **103,1**, p.41 **92,4**, p.42 **90,3**, aba Dataset **73,4**, rasterizar **64,7**, aba Galeria **24,7** |
| fps ≥ 55 @ p95 | juntos **91,8 · 90,2 · 94,0** → mediana **91,8 fps**; pan 549–661; zoom 66,9–73,4. **PASSOU** (67 % de folga) |
| Vazio de painel (item 6) | **10 de 12** acima de 200 kpx a 1920; **0 de 24** a 1366 e 1280 |
| Ocupação (item 7) | **73,1 %** clara / **69,7 %** escura; vão 16 px; 114,5 kpx à direita da paleta |
| Estado vazio na tela (item 1) | **30 de 30 `DESENHADO=sim`** |
| Ícones da janela | **0 glifos de texto**; caixa única 16×16, amplitude 0 px; tinta 17,6 %–41,4 % |
| FEN | **48 medições, 0 cortes silenciosos** |
| Sabotagens do detector | C5 **6/6**, C7 do crítico **8/8**, C8 minha **8/8**, 3 controles negativos mudos |

---

## O que continua aberto, com o número

| # | item | número |
|---|---|---|
| tinta dos ícones | 17,6 % a 41,4 %, amplitude relativa **80,8 %** contra ±20 % | medido hoje |
| item 6 | **10 de 12** painéis acima de 200 kpx a 1920 (Texto 425,0; Revisão 394,0; Dataset 370,3) | medido hoje |
| item 7 | **114,5 kpx** de tinta zero à direita da paleta a 1920 claro | medido hoje |
| item 8 (Motivo) | coluna de 694 px a 1920 → **19 de 27** linhas não cabem; 25 de 27 a 1366 e 1280 | medido hoje |
| item 10 | o Dataset mostra **duas frases**: `Lendo o dataset` no painel e `leitura do dataset (labels.csv)` no rodapé | medido hoje |
| item 11 | Estudo com **29 botões** em **4 filas** a 1920 e **6** a 1366/1280, contra o alvo de ≤ 12 em ≤ 2 | medido hoje |
| um rótulo, um controle | **2** pares com estados divergentes, os dois na pele Foco | medido hoje |
| janela pequena | `minimumSize` **1066×735**: num monitor de 1024×768 a janela transborda **42 px** de largura | medido hoje |
| barra determinada no dataset | precisa de callback em `dataset_browser.load_rows`, fora do que esta frente escreve | declarado |
| E/S na thread da janela | **23,0 ms** de `_abrir_cache_de_posicoes` (SQLite) + 17,1 ms de `nt.stat` dentro de `abrir PDF` | medido hoje |
| bloqueio | **REPROVA**, 7 operações; a maior é `abrir PDF` com 203,8 ms | medido hoje |

---

## O que só o olho achou

A ordem de serviço diz que olhar acha, em todo ciclo, o que a medição não pega. Aconteceu duas
vezes, e as duas em coisas que **eu mesmo tinha acabado de escrever**:

**A. O `✕` da paleta saiu com 16 px no meio de doze vizinhos de 26.** Ampliado o recorte
`z_paleta_x.png`, o desenho novo era visivelmente menor que as peças ao lado — que é o defeito do
§9.4 do ciclo 5 (*"um 'ícone' de 4×5 px num botão de 26 px"*) em miniatura, um botão adiante. O
censo não pegava porque ele mede a **caixa do ícone**, e 16×16 é a caixa certa **para o cromo**.
`qt/icones.vestir` ganhou `lado=`.

**B. O paginador da Galeria continuava com glifo de texto, e o censo o classificava como texto.**
`"◀ anterior"` tem letra, então a régua o contava como rótulo e não como glifo-ícone. Ampliado, o
botão lê-se **`- anterior`**: o `◀` do Segoe UI rende um traço horizontal chato de 5×3 px. Hoje os
quatro do paginador têm desenho, e os dois do meio mantêm a palavra ao lado (`manter_texto`).

---

## O que mudou, arquivo a arquivo

**Nossa suíte**

* `src/caissa/ui/audit/progresso.py` — `PISTAS_DE_TOTAL` **saiu**; `_e_contagem`,
  `_numero_calculado_na_mesma_funcao`, `_interpolacoes`; `faixa_da_barra_do_rodape` e
  `faixas_medidas` (a faixa **medida** do widget); `METODOS_DE_POOL`, `FUNCOES_DE_PROCESSO_EXTERNO`,
  `EMBRULHOS_DE_CHAMADA`; `Popen`, `QProcess`, `ThreadPool` em `CLASSES_DE_THREAD`; `to_thread`,
  `moveToThread`, `create_task`, `ensure_future`, `run_coroutine_threadsafe` em
  `METODOS_DE_SUBMISSAO`; apelido por atribuição e por contêiner literal em `apelidos_de_thread`;
  `_termo_final` descasca `Subscript`.
* `src/caissa/ui/audit/bloqueio.py` — atribuição das **sete**; `COBERTURA_MINIMA` e a linha de
  cobertura; `_perfilar` com janela fria e com o escoamento dentro do perfil.
* `src/caissa/ui/audit/capture.py` — `FRACAO_DO_DIVISOR`, `_fixar_o_divisor`, estado próprio.
* `tests/unit/ui/test_medicao.py` — 7 testes novos (o nome da variável parametrizado, o `detail`
  interpolado que não é contagem, o contador embutido, a faixa do widget nos dois sentidos, a faixa
  não medida, as oito formas do crítico do ciclo 7, as oito minhas, os três controles negativos).
* `benchmarks/reports/ui/c8/` — as 36 capturas com manifesto, `sab_c8/` (a sabotagem no
  repositório, ao lado da C5 e da C7), e os instrumentos `c8_vazio_na_tela.py`,
  `c8_barra_do_visor.py`, `c8_fen_avisa.py`, `c8_icones_da_janela.py`, `c8_zoom.py`.

**Tronco** (`chess_diagram_ocr/`)

* `qt/painel_do_pdf.py` — `nomear_o_que_o_cromo_nao_desenha`, `_so_de_icone`.
* `qt/janela.py` — o cromo montado avisa o painel (duas linhas: uma em `_montar_o_cromo`, outra em
  `_esvaziar_o_cromo`).
* `qt/rotulo.py` — `CampoQueAvisaQueContinua`; `RotuloElidido(largura_desejada=…)`.
* `qt/rodape.py` — `barra_de_progresso()`; o rótulo do documento pede o texto inteiro.
* `qt/icones.py` — `vestir` e `vestiu_de_icone`.
* `qt/painel_de_estudo.py`, `qt/painel_de_resultado.py`, `qt/painel_do_dataset.py`,
  `qt/painel_da_galeria.py`, `qt/paleta_de_pecas.py`, `qt/painel_de_revisao.py` — os onze glifos
  viraram desenho; os dois campos de FEN; `Cancelar a varredura`; `cabeçalhos`; as dicas de
  conteúdo dos dois campos de `outro`.
* `qt/painel_do_dataset.py` — `_registrar_a_leitura` deixa de imprimir a contagem ao lado da
  marquise.
* `ui/icones.py` — `inicio_da_linha`, `fim_da_linha`; setas de diagrama na grade única.
* `ui/comandos.py` — quatro comandos da Estudo com `icone=`.
* `ui/strings.py` — `ASPA_ABRE`/`ASPA_FECHA` e as duas frases de estado vazio.
* `tests/test_qt_janela.py` — `_lido_na_tela` sem `toolTip()`, três peles × três larguras, a prova
  de vida, e a regex das duas aspas.
* `tests/test_busy.py` — a régua gêmea alargada, `SABOTAGEM_C8` e dois testes.
* `tests/test_qt_rodape.py` — três testes de elisão contra folga.
* `tests/test_qt_painel_de_estudo.py` — três testes da marca da FEN.
* `tests/test_qt_painel_do_pdf.py` — seis testes da nomeação pelo cromo.
* `tests/test_ui_icones.py` — a conta de ícones vai a 22, com o motivo escrito.
* `tests/test_packaging.py` — `LIMITE` de `qt/janela.py` **1882 → 1883**.

### Sobre a catraca de linhas de `qt/janela.py`

Ela subiu **uma** linha, e o protocolo dela é o que a própria mensagem de falha manda: *"baixe o que
for possível para `ui/` ou registre o novo placar aqui, com o motivo"*. A primeira forma do conserto
punha **24** linhas na janela (um método com o docstring); a catraca as achou, e o que sobrou foi
uma chamada — a regra inteira mora em `qt/painel_do_pdf`, onde ela é testável sem abrir janela, e a
segunda chamada foi para dentro de `_esvaziar_o_cromo`, numa linha que já existia. O motivo está
escrito no docstring de `LIMITE`, no formato das entradas anteriores. **Nenhuma outra asserção foi
afrouxada**: a de `test_ui_icones` mudou de 20 para 22 porque dois desenhos entraram, e o teste
passou a cobrar os dois pelo nome.

---

## Suítes

| suíte | resultado |
|---|---|
| Nossa (`.venv`, `pytest tests -q`) | **3011 passed, 1 skipped, 1 failed** em 788,86 s |
| Tronco (`-p no:randomly`) | **4462 passed, 3 failed, 2 skipped, 4401 subtests** em 299,09 s |

**A reprovação da nossa suíte não é desta frente, e a prova é o carimbo do arquivo.** É
`tests/unit/typeset/test_proofsheet.py::test_the_blind_harness_emits_a_sample_from_both_sources`,
que morre com `AttributeError` em `tools/build_blind.py:238` lendo um atributo de `composed`.
`src/caissa/typeset/board_svg.py` foi modificado às **11:42** e `fonts.py` às **11:22** desta
sessão — pelo agente que está criticando `src/caissa/typeset/` agora. Não toquei em `typeset/`
nem em `tools/`. **Zero reprovações em `tests/unit/ui/`**, e a contagem subiu de 2996 para 3011
(os 15 a mais são os testes deste ciclo, 7 na nossa suíte e 8 no tronco).

**As três do tronco são as três de sempre**, e acusam exatamente as **seis** entradas que o
crítico enumerou — nenhuma delas minha:

```
  test_strings::test_no_ui_string_uses_an_unaccented_portuguese_word
      biblioteca.py: 'cabecas'      substituicao.py: 'pagina' (x4)      tokens.py: 'SELECAO'
  test_editor_model::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter
      desenho_de_diagrama.py, pdf_substituicao.py
  test_docs::test_a_arvore_do_README_lista_todo_modulo_do_pacote
```

As strings que **eu** escrevi neste ciclo — `Cancelar a varredura`, `Limpar os cabeçalhos`,
`Copiar cabeçalhos para todos`, `nome do cabeçalho`, `valor` — passam pelo `AccentTests`.

---

## Como reproduzir

```bat
:: portoes -- --saida SEMPRE para benchmarks\reports\ui\c8
.venv\Scripts\python.exe -m pytest tests -q
set PYTHONPATH=<suite>\src;<tronco>\src
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.contraste --saida ...\c8
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.progresso --saida ...\c8
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado  --pdf "...\1937 Kemeri.pdf" --saida ...\c8
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio --pdf "..." --saida ...\c8   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.quadros  --pdf "..." --saida ...\c8   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.capture  --marca c8 --pdf "..." --saida ...\c8
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly   :: no tronco

:: sabotagens (nenhuma escreve sobre o tronco nem sobre as capturas)
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco benchmarks\reports\critique\ui\c5\sabotado --saida <tmp>   :: 6 de 6
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco benchmarks\reports\critique\ui\c7\sab_c7 --saida <tmp>     :: 8 de 8
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco benchmarks\reports\ui\c8\sab_c8       --saida <tmp>        :: 8 de 8

:: instrumentos deste ciclo (benchmarks\reports\ui\c8\ -- so o c8_zoom.py grava, e grava aqui)
c8_vazio_na_tela.py      :: 30 de 30 DESENHADO=sim  (o do critico com a regex das duas aspas)
c8_barra_do_visor.py     :: 1 fila de 1243 a 1920; nunca dois controles com o mesmo nome
c8_fen_avisa.py          :: 48 medicoes, 0 cortes silenciosos
c8_icones_da_janela.py   :: 18 botoes so-de-icone, caixa unica 16x16, 0 glifos
c8_zoom.py <png> x0 y0 x1 y1 [fator] [nome]

:: instrumentos do critico, rodados sem alteracao (conferido que nao gravam)
critique\ui\c7\c7_vazio_na_tela.py     :: NAO imprime nada hoje -- a regex dele so conhece a aspa reta
critique\ui\c7\c7_icones_da_janela.py  :: 0 glifos de texto (eram 11)
critique\ui\c7\c7_rodape_elisao.py     :: 0 ELIDE nas tres larguras
critique\ui\c7\c7_rotulos_repetidos.py :: 2 pares divergentes (eram 3)
critique\ui\c7\c7_janela_pequena.py    :: minimumSize 1066x735; 0 controles fora
critique\ui\c5\c5_vazios.py  <png..>   :: 10 de 12 acima de 200 kpx a 1920
critique\ui\c5\c5_regioes.py <png..>   :: 73,1 %, vao 16 px, 114,5 kpx
ui\c6\c6_rodape.py <png..>             :: 8 ociosas / 28 ocupadas / 0 contradicoes
ui\c6\c6_aberto.py                     :: itens 8, 10 e 11
```

**Sobre caminhos de saída**, que já custaram 17 capturas em dois ciclos: conferi o destino de cada
script antes de rodá-lo. Os instrumentos `c5_*`, `c7_*` e `c6_*` não gravam nada; os módulos do
arnês receberam `--saida` em toda invocação, sempre para `benchmarks\reports\ui\c8\`; as sabotagens
gravaram em pasta temporária. **Nada foi escrito em `benchmarks\reports\critique\` nem em
`docs\quality\F9_CRITIQUE_*.md`.**
