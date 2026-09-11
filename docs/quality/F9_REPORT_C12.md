# F9 — Interface, relatório do ciclo 12

```
FRENTE: F9 (Interface)
CICLO:  12
ENTRADA: F9_CRITIQUE_C11.md — REPROVADO por um item
```

**O bloqueante era o décimo instrumento cego desta frente, e o segundo cego por escopo.** O portão
de teclado publicava `216 / 240 / 360 focáveis, 0 sem nome, PASSOU` percorrendo `janela.abas` — as
seis abas da janela principal — e em onze ciclos nenhum portão desta frente abriu um dos **doze
`QDialog`** do produto. Rodada a régua do próprio portão em seis deles, o crítico achou **11
controles sem nome acessível**, incluindo o campo da paleta de comandos (`Ctrl+Shift+P`) e **dois
`QLineEdit` sem nome lado a lado** em `Achar e substituir`.

**Está fechado, e a prova é do instrumento do próprio crítico.** `c11_dialogos.py`, sem uma linha
alterada, sobre o produto de hoje:

```
  ======== defeitos nos dialogos, pele classica: 0 ========      (era 11)
  DEFEITOS nos 6 dialogos:  antes=0   depois de nomear_tudo=0    (era antes=11)
```

E o portão desta frente passou a medir a superfície inteira, em **seis arranjos** e não três:

```
  classica/compacta      6 abas       216 focáveis   0 sem nome  0 sem papel  0 nome vazio  0 fora do Tab  PASSOU
  classica/compacta     13 diálogos    46 focáveis   0 sem nome  0 sem papel  0 nome vazio  0 fora do Tab  PASSOU
  classica/confortavel   6 abas       216 focáveis   0 · 0 · 0 · 0                                          PASSOU
  classica/confortavel  13 diálogos    46 focáveis   0 · 0 · 0 · 0                                          PASSOU
  foco/compacta          6 abas       240 focáveis   0 · 0 · 0 · 0                                          PASSOU
  foco/compacta         13 diálogos    46 focáveis   0 · 0 · 0 · 0                                          PASSOU
  foco/confortavel       6 abas       240 focáveis   0 · 0 · 0 · 0                                          PASSOU
  foco/confortavel      13 diálogos    46 focáveis   0 · 0 · 0 · 0                                          PASSOU
  fita/compacta          6 abas       360 focáveis   0 · 0 · 0 · 0                                          PASSOU
  fita/compacta         13 diálogos    46 focáveis   0 · 0 · 0 · 0                                          PASSOU
  fita/confortavel       6 abas       360 focáveis   0 · 0 · 0 · 0                                          PASSOU
  fita/confortavel      13 diálogos    46 focáveis   0 · 0 · 0 · 0                                          PASSOU

  Veredito de TODOS os arranjos: PASSOU
```

**Os 216 / 240 / 360 das abas batem à unidade com o que o crítico remediu**, e ao lado deles há
agora **46 focáveis em 13 telas de diálogo, por arranjo** — a metade do produto que nenhum portão
desta frente jamais abriu.

---

## §1 — O bloqueante, nas duas metades que a ordem de serviço exigiu

### 1.1 Produto: **um** filtro de evento, e não doze chamadas

`qt/acessibilidade.vigiar_dialogos` instala um filtro de evento **na aplicação** que, em
`QEvent.Show` de qualquer `QDialog`, prepara aquele diálogo. Ele é instalado uma vez, e
`qt/janela.py` diz **uma linha só** — `acessibilidade.tornar_acessivel(self)` —, que é a linha
que já existia, com outro nome.

**A linha única não é elegância, é uma decisão com duas razões.** A primeira: duas linhas em
`qt/janela.py` seriam duas coisas para lembrar, e quem escrever a próxima janela copia a
primeira — que é a forma exata do defeito do ciclo 11. A segunda apareceu na medição e vale
registrar: **`qt/janela.py` está sob uma catraca de tamanho da S-31**
(`test_packaging.py::TamanhoDaJanelaTests`, corte em 1 883 linhas, o arquivo exatamente lá).
A primeira forma deste conserto acrescentava seis linhas ao arquivo e **derrubou a catraca** —
`1889 not less than or equal to 1883`. Baixar o corte no teste seria afrouxá-lo; o conserto foi
não crescer. `qt/janela.py` fica em **1 883 linhas**, as mesmas de antes deste ciclo.

**É a forma que o próprio módulo defende por escrito.** O docstring de `qt/acessibilidade.py` diz,
desde o ciclo 2: *"as vinte chamadas seriam vinte lugares que alguém precisa lembrar, e a vigésima
primeira — o campo que o próximo item acrescenta — nasceria muda"*. Doze `nomear_tudo(self)`
espalhados pelos diálogos seriam exatamente esse antipadrão, um andar acima — e o teste
`test_nenhum_dialogo_chama_nomear_tudo_por_conta_propria` **reprova** quem os escrever.

Por que `Show` e não o construtor: no `Show` os leiautes já estão montados, e é do leiaute que
`rotulo_vizinho` tira o nome de um campo. É assim que os dois `QLineEdit` de `Achar e substituir`
viram `'Achar'` e `'Trocar por'` sem uma linha por campo.

### 1.2 Arnês: uma linha por diálogo, e a lista sai do produto

`chess_diagram_ocr.qt.dialogos_do_produto()` devolve **os doze**, achados na **árvore sintática**
de `qt/*.py` — não numa tabela escrita à mão:

```
  ControladorDeTreino  DialogoDeBases  DialogoDeEscopo  DialogoDePartidas  DialogoDeTreino
  JanelaDaPaleta  JanelaDeAtalhos  JanelaDeBusca  JanelaDeEstatisticas
  _JanelaDeColar  _JanelaDeColecao  _JanelaDePartidas
```

`caissa.ui.audit.teclado.dialogos_registrados()` lê essa lista, do mesmo jeito que
`peles_registradas()` lê `ui/pele.PELES`. O arnês só guarda o que ninguém consegue derivar — **com
que argumentos cada janela abre** (`RECEITAS`) — e `_medir_os_dialogos` **levanta** quando as duas
listas divergem, nomeando o diálogo.

**Ler a árvore sintática e não importar o PyQt6 é uma decisão com consequência**: é o que faz o
teste de deriva rodar no venv desta suíte, que não tem binding de Qt nenhum. Uma varredura que
importasse Qt deixaria esse teste pulado, que é o mesmo que não existir.

### 1.3 Testado por mutação, e não por leitura

`benchmarks/reports/ui/c12/c12_prova_de_vida_dos_dialogos.py`, quatro mutações:

```
  sha256 de qt/*.py ANTES : 804238d0a838e35a41b667b82048b79b7214959c317c156b58a6f637bd603179

(0) NENHUM diálogo é varrido -- o produto como o ciclo 11 o achou
    telas medidas: 13     SEM NOME: 8   SEM PAPEL: 2   telas que reprovam: 6
       DialogoDeBases          ['QScrollArea', 'QScrollArea(sem papel)']
       DialogoDePartidas       ['QLineEdit', 'TabelaQt']
       JanelaDeAtalhos         ['QScrollArea', 'QScrollArea(sem papel)']
       JanelaDeBusca (Achar)   ['QLineEdit']
       JanelaDeBusca (subst.)  ['QLineEdit', 'QLineEdit']      <<< os dois lado a lado do ciclo 11
       _JanelaDePartidas       ['QListWidget']

(a) a varredura não alcança `JanelaDeBusca`
    REPROVARAM: {'JanelaDeBusca (Achar no texto)': 1, 'JanelaDeBusca (substituindo)': 2}
    só na JanelaDeBusca: True        com a varredura de volta: 13 diálogos, 0 reprovados

(b) um DÉCIMO TERCEIRO QDialog entra no produto (arquivo novo em qt/, apagado no fim)
    a lista do produto passou a ter 13: sonda dentro? True
    o portão LEVANTOU: sem receita no arnes = ['_JanelaDeSondaC12']

(c) a receita de `JanelaDaPaleta` some do arnês
    o portão LEVANTOU: sem receita no arnes = ['JanelaDaPaleta']

  sha256 de qt/*.py DEPOIS: 804238d0a838e35a41b667b82048b79b7214959c317c156b58a6f637bd603179
  a pasta do tronco voltou identica: True        PROVA DE VIDA: PASSOU
```

**A mutação (b) é a resposta à pergunta exata da ordem de serviço** — *"acrescente um diálogo e
prove que o portão o acha sem ser avisado"*. Ele acha, e derruba o portão nomeando-o.

**Sobre o 10 e o 11, sem atenuar.** A mutação (0) acusa **10** e o crítico contou **11**, e a
diferença se explica nos dois sentidos. Cinco dos onze receberam nome **escrito no produto**
(o campo da paleta, a lista da busca, o corpo das estatísticas, o campo de colar e a lista da
coleção); nome escrito não depende da varredura, então bloqueá-la não os desnomeia. Em troca, o
portão acusa **três diálogos que o crítico nunca abriu** — `DialogoDeBases`, `DialogoDePartidas` e
`_JanelaDePartidas`. Os dois `QLineEdit` lado a lado de `Achar e substituir`, que eram o pior caso,
aparecem aqui e somem com a varredura de volta.

### 1.4 O que a régua inteira achou nos diálogos, além dos onze

O crítico aplicou `anonimos()` e `sem_papel()`. Aplicada a régua **inteira** — que inclui *o nome
que não nomeia* e *a volta do `Tab`* —, os treze diálogos devolveram mais nove achados. Cada um
foi resolvido, e digo por qual caminho:

| achado | onde | conserto |
|---|---|---|
| `QLineEdit` → `'Campo de texto'` (eco do papel) | paleta de comandos | **produto**: `setAccessibleName("Comando a procurar")` |
| `QListWidget` → `'Lista'` (eco do papel), 2× | `JanelaDeBusca` | **produto**: `"Ocorrências achadas"` |
| `QPlainTextEdit` → `'Editor de texto'` | `JanelaDeEstatisticas` | **produto**: `"Estatísticas do dataset"` |
| `QTextEdit` → a instrução inteira (prosa) | `_JanelaDeColar` | **produto**: `"Posição ou partida colada"` |
| `QListWidget` → `'0 partida(s) em… Escolha uma'` | `_JanelaDeColecao` | **produto**: `"Partidas do arquivo"` |
| `QPushButton 'OK'` (sem letras) | `_JanelaDeColar` | **produto**: o botão passa a dizer **`Colar`**, na tela e no anúncio |
| `QCheckBox` com nome de arquivo de 66 caracteres | `DialogoDeBases` | **régua**: o teto de comprimento não vale para o texto **desenhado** (WCAG 2.5.3) |
| `QRadioButton` marcado fora do `Tab` | `DialogoDeEscopo` | **régua**: um grupo exclusivo é **um** ponto de parada; as setas alcançam o resto |
| volta do `Tab` não fecha com **um** controle | `JanelaDeEstatisticas` | **régua**: uma lista circular de um elemento fecha no primeiro passo |

**As três mudanças de régua são afinação e não afrouxamento, e cada uma tem um teste que repõe o
defeito que a criou** (`TestOsMotivosRefinadosContinuamPegandoODefeitoQueOsCriou`): a dica de 67
caracteres do ciclo 3 continua reprovando; o nome derivado de um rótulo vizinho longo continua
reprovando; `-`, `+`, `|◀`, `.md` e `121` continuam "sem letras"; `"Campo de texto"` continua "eco
do papel"; e um beco de dois controles continua reprovando a volta.

**`_JanelaDeColar`: "OK" virou "Colar" na tela, e não só no anúncio.** Trocar apenas o
`accessibleName` faria o leitor de tela dizer uma palavra e o olho ler outra, que é o que a WCAG
2.5.3 proíbe. O verbo é melhor para os dois.

### 1.5 O que o portão publica agora

Uma linha por diálogo, com a mesma régua e o mesmo formato das abas — **literalmente a mesma
função**, `_medir_uma_tela`, que antes existia em duas cópias:

```
  --- os 12 QDialog que o produto declara, em 13 telas --------------------
  ControladorDeTreino (nunca mostrado)      0 focáveis  ...  PASSOU
  DialogoDeBases (Estudo | Bases)          12 focáveis  ...  PASSOU
  DialogoDeEscopo (Galeria | Varrer)        4 focáveis  ...  PASSOU
  DialogoDePartidas (Galeria | Partidas)    5 focáveis  ...  PASSOU
  DialogoDeTreino (Dataset | Treinar)       0 focáveis  ...  PASSOU
  JanelaDaPaleta (Ctrl+Shift+P)             2 focáveis  ...  PASSOU
  JanelaDeAtalhos (Ver | Atalhos)           2 focáveis  ...  PASSOU
  JanelaDeBusca (Achar no texto)            5 focáveis  ...  PASSOU
  JanelaDeBusca (substituindo)              7 focáveis  ...  PASSOU
  JanelaDeEstatisticas (Dataset)            1 focável   ...  PASSOU
  _JanelaDeColar (Estudo | Colar)           3 focáveis  ...  PASSOU
  _JanelaDeColecao (Estudo | Abrir PGN)     3 focáveis  ...  PASSOU
  _JanelaDePartidas (Estudo | Partidas)     2 focáveis  ...  PASSOU
```

Treze telas para doze classes: `JanelaDeBusca` aparece duas vezes porque `Achar` e `Achar e
substituir` são duas telas, e a segunda é a que tem os dois campos lado a lado.

**Duas linhas com `0 focáveis`, e elas são a resposta certa e não uma omissão.**
`ControladorDeTreino` é um `QDialog` que **nunca é mostrado** — o docstring dele diz que a herança
existe só para ter sinais, e quem aparece é o `DialogoDeTreino`. `DialogoDeTreino` tem três rótulos
e uma barra indeterminada, e nenhum deles aceita foco: quem cancela o treino é o rodapé. Os dois
ficam na conta de propósito: uma exceção calada no arnês é como a lista de peles voltaria a ter
dois terços do produto.

---

## §2 — `test_field_eval`: remedido numa árvore limpa, e **fechado**

O ciclo 11 chamou a recusa do ciclo 10 de *"a decisão certa, prova correta, item ainda aberto"*, e
nomeou o caminho: **remedir numa árvore limpa**, que foi o que o próprio relatório do C10 escreveu
e não fez. Feito.

**A árvore limpa foi construída sem tocar em `HEAD`, em índice nem em ramo do tronco.** Com
`GIT_INDEX_FILE` numa pasta temporária: `read-tree HEAD`, `add -u`, `write-tree`, `commit-tree` —
um objeto de commit com **exatamente** a árvore de trabalho de hoje, e um `worktree add --detach`
sobre ele. Conferido antes de medir:

```
  tronco (sujo)       digest 43f2ae26db1ef9ef   30 modulos   dirty=True
  arvore limpa        digest 43f2ae26db1ef9ef   30 modulos   dirty=False  commit=7bcb396fed76
  modulos com digest diferente entre as duas: 0
```

**O código medido é bit a bit o de hoje, e o `dirty` sai `false` porque a árvore é limpa de
verdade.** As quatro remedições rodaram lá (`cvoff-field --json`, um modelo cada), com os arquivos
escritos **fora** da árvore para que ela continuasse limpa durante as quatro.

**A remedição não moveu métrica nenhuma**, e o número é meu:

```
  4 relatorios, campo a campo contra o publicado:
     metricas comparadas (fora dos campos de tempo): 4 372
     metricas diferentes                           :     4   <- todas `measurement.code_commit`
     campos de tempo diferentes                    :   264   (seconds, seconds_per_diagram)
  pages/annotated: 68 / 115 nos quatro, igual ao publicado
  digest do modelo: a907f61086da609f · f5e19f9b9a427580 · 843fbee08f9e231f · 1c0b40073e349a28
                    — idênticos aos publicados
```

As **quatro** diferenças fora do tempo são o campo de proveniência `code_commit`, que é o que a
remedição existe para atualizar. **Nenhuma métrica de qualidade se moveu**, o que confirma a conta
que o ciclo 10 tinha publicado (1 080 métricas, 0 diferentes) sobre um modelo só, agora sobre os
quatro.

```
  tests/test_field_eval.py -> 101 passed, 142 subtests passed   (era 1 failed, 100 passed)
```

**O commit efêmero ficou alcançável de propósito**: `git tag f9-c12-arvore-limpa` aponta para
`7bcb396`. Sem isso, o `measured_with.commit` que os quatro relatórios publicam apontaria para um
objeto que o coletor de lixo do git apagaria — proveniência que não resolve é pior que
proveniência nenhuma. A árvore de trabalho temporária foi removida (`git worktree remove`), e
`git worktree list` não a mostra mais.

---

## §3 — Os quinze itens não bloqueantes, um a um, com o número

### Item 1 — a fita promete "grupos nomeados" e desenhava 0 de 5 · **fechado com uma ressalva declarada**

Medido no cromo vivo (`benchmarks/reports/ui/c12/c12_fita.py`), nas seis combinações:

| arranjo | largura | modo | cabeçalhos desenhados | filetes entre grupos |
|---|---|---|---|---|
| fita/compacta | 1280 · 1366 · 1920 | compacto | **0 de 5** | **4 de 4** |
| fita/confortavel | 1280 · 1366 | compacto | **0 de 5** | **4 de 4** |
| fita/confortavel | **1920** | **pleno** | **5 de 5** | 0 (não fazem falta) |

**A promessa é verdadeira no modo pleno, e o modo compacto tem uma decisão medida contra ela.** A
S-228 troca o cabeçalho por dica no compacto porque ele custa **uma linha de texto por fita**, e
essa linha é a diferença entre a fita caber e competir com a página; a decisão tem teste no tronco
(`test_o_cabecalho_do_grupo_vira_dica_no_compacto`) e eu não a derrubei — derrubá-la seria trocar
um item de desenho por outro sem medir o que se perde.

**O que a S-228 não decidiu foi deixar o olho sem fronteira nenhuma**, e essa metade da acusação
estava certa: vinte e quatro botões em duas filas seguidas leem-se como uma barra de duas alturas.
O ciclo 12 acrescentou o **filete vertical entre grupos** no modo compacto: **4 de 4**, a 1 px de
largura e **zero** de altura — o recurso que a S-228 está protegendo. E `ui/pele.FITA` deixou de
prometer no vazio: a declaração agora diz em qual arranjo os cinco cabeçalhos aparecem e por que
no outro eles não aparecem, com o número.

*Continua aberto, declarado:* **0 de 5 cabeçalhos desenhados na densidade Compacta**, que é a que
esta pele traz. Quem escolhe "Confortável" a 1920 vê os cinco.

### Item 2 — seis botões 12 px mais curtos e 6 px encravados · **fechado**

Era uma regressão que o conserto do bloqueante do ciclo 10 introduziu, e só o olho a pegou.
Medido no widget, a 1366:

```
  ANTES   topos distintos [0, 6, 49, 55]   alturas distintas [31, 43]
  DEPOIS  topos distintos [0, 49]          alturas distintas [43]
```

Os dois topos que restam são as **duas filas** da fita quebrada; dentro de cada fila há **um topo
e uma altura**, que é o alvo com as palavras do crítico. No modo pleno a 1920: `topos=[0]`,
`alturas=[81]` — uma fila, um topo, uma altura.

O conserto é `Fita._igualar_a_altura`: todos os botões passam a ter a altura do mais alto, que é o
de duas linhas de rótulo — o teto que `LINHAS_DO_ROTULO` já fixa. **A altura sai do widget e não da
conta de `ui/medidas_da_fita.py`**, e essa distinção o módulo já defende: as três medidas de lá
saíram de um `ttk.Button`, e cravá-las num `QToolButton` seria cobrar do desenho errado. O que se
afirma aqui é a *relação* — todos iguais ao mais alto —, e ela é do toolkit.

**E eu olhei.** `benchmarks/reports/ui/c12/z12_fita_ribbon_1366_ANTES.png` e
`z12_fita_ribbon_1366.png`, a 3×: a faixa cinza acima e abaixo das duas lupas sumiu, e as quatro
setas do paginador deixaram de ficar encravadas. O `Desfazer`/`Refazer`/`Limpar`, que eram os
outros três curtos, ficaram na linha dos vizinhos.

### Item 3 — a caixa do ícone é 0×11 px numa densidade e 2×17 px na outra · **medido nos seis arranjos; a amplitude continua aberta**

O censo de ícones passou a percorrer **pele × densidade**, lendo as duas listas do produto
(`ui/pele.PELES` e `ui/pele.DENSIDADES`). Seis arranjos, 24 grades:

```
  classica/compacta      3 grades  (11 px, 26 px, 11 px)     todas 0x0
  classica/confortavel   3 grades  (16 px, 26 px, 16 px)     todas 0x0
  foco/compacta          4 grades  ... + pilula 18 px        0x3   <<<
  foco/confortavel       4 grades  ... + pilula 18 px        0x3   <<<
  fita/compacta          5 grades  ... + fita 20 px          0x11  <<<
  fita/confortavel       5 grades  ... + fita 32 px          1x1 (dentro do alvo) e 2x17  <<<

  caixa única em 20 de 24 grades          GLIFOS DE TEXTO em TODOS os arranjos: 0
```

**O 2×17 px que o crítico achou está confirmado e agora é do portão, não de uma invocação
avulsa.** A amplitude **continua aberta**, e digo por quê sem atenuar: a "caixa" aqui é a caixa de
**tinta** do desenho, e `ui/icones.na_grade` enche o lado maior mantendo a proporção. Uma seta tem
tinta larga e baixa; fazer a caixa fechar em 24 de 24 exigiria ou **distorcer** cada desenho até o
quadrado, ou **redesenhar** os vinte e tantos ícones com silhueta quadrada. As duas são decisões de
arte, não de leiaute, e nenhuma delas é obviamente melhor que 20 de 24.

**O eixo densidade era o item estrutural, e ele fechou**: `teclado` e o censo de ícones percorrem
os seis arranjos, com a lista saindo do produto, e `TestTodasAsDensidades` cai no dia em que uma
terceira densidade entrar no menu sem entrar nos portões.

### Item 4 — a fronteira declarada do portão de execução era mais larga que o produto dela · **fechado de 1 de 4 para 3 de 4, com a fronteira encolhida**

A frase de antes dizia *"para atravessá-la é preciso sair do Python"*, e era falsa: três das
quatro formas do crítico são biblioteca-padrão pura. Dois pontos novos entraram na interceptação
— **dez, e não oito**:

```
  a  _thread.start_new_thread          calada -> PEGA   (_thread.start_new_thread)
  b  multiprocessing.Process().start() calada -> PEGA   (multiprocessing.Process.start)
  c  ProcessPoolExecutor().submit()    PEGA   -> PEGA   (agora pelo processo, não pela thread interna)
  d  ctypes -> kernel32.CreateThread   calada -> calada  <<< a fronteira de verdade
  controles negativos n1..n3           calados 3 de 3
  formas pegas: 3 de 4                                   (era 1 de 4)
```

**O que resta fora é uma chamada à API do sistema por `ctypes`**, e ali não nasce objeto de Python
para interceptar — `threading.enumerate()` não a lista porque o `threading` não a conhece. A frase
da fronteira passou a dizer isso, com o nome da função. A árvore de sabotagem entrou no arnês
(`benchmarks/reports/ui/c12/sab_c12/`), como a C5, a C7, a C8 e a C9 entraram.

As sabotagens anteriores continuam fechadas: `sab_c9x` **8 de 8** com 4 controles calados, `sab_c10`
**8 de 8** com 5 calados.

### Item 5 — `bloqueio.py` reescrevia `data/janela.json` · **fechado, e a certidão virou teste**

`caissa/ui/audit/bloqueio.py` construía `JanelaPrincipal()` **sem argumento** nas duas únicas
construções do arnês inteiro que faziam isso. As duas passaram a receber
`caminho_do_estado=capture.estado_de_medicao(...)`. Medido:

```
  data/janela.json  ANTES  sha256 77d246222e1efad6740f60eb2be3b3c72a2cd9a1a730d485cb92e45c9907cecd
  ... rodado o portao de bloqueio inteiro (3 execucoes, 7 operacoes) ...
  data/janela.json  DEPOIS sha256 77d246222e1efad6740f60eb2be3b3c72a2cd9a1a730d485cb92e45c9907cecd
  mtime 20:12, o de antes da corrida
```

**Byte a byte idêntico**, e é o mesmo `77d24622…cd` que o crítico registrou ao restaurar o arquivo.

**A certidão de higiene do ciclo 10 conferia o arquivo errado** — o `data/app_tkinter_state.json`,
que é o estado do **Tk**, de um frontend cortado em 2026-08-31. O estado da janela Qt é
`data/janela.json` (`qt/janela.py: CAMINHO_DO_ESTADO`), e é ele que guarda `last_pdf`, `last_page`,
`pdf_zoom`, `pdf_enquadramento`, `board_zoom` e `pdf_history`. **A certidão deixou de ser uma frase
num relatório e virou teste**: `TestNenhumPortaoEscreveNaSessaoDeQuemORoda` lê os oito módulos do
arnês, reprova a construção de janela que não redirecionar o estado, exige que a certidão nomeie
`data/janela.json`, e cai se o produto trocar de arquivo de estado.

### Item 5b — **o que o olho achou e nenhuma régua procurava: 7 de 12 botões em inglês** · fechado

A ordem de serviço manda recapturar o que mudou **e olhar**. Os doze `QDialog` nunca foram
fotografados por instrumento nenhum desta frente — `capture.py` fotografa as seis abas. Escrevi
`c12_retrato_dos_dialogos.py`, fotografei os treze e olhei. A primeira imagem
(`JanelaDeBusca`, substituindo) tem um botão escrito **`Close`**.

O portão tinha acabado de dar `PASSOU` naquele diálogo, e com razão: `Close` tem cinco letras,
não é eco do papel, não é o valor do controle e não é prosa. **Nenhuma régua desta frente olhava
para idioma.** Medido nos treze:

```
  botoes padrao de QDialogButtonBox: 12      EM INGLES: 7
     JanelaDeAtalhos -> Close     JanelaDeBusca (x2) -> Close    _JanelaDePartidas -> Close
     _JanelaDeColar  -> Cancel    _JanelaDeColecao -> Open, Cancel
```

Os textos de um `QDialogButtonBox` vêm do catálogo de tradução do Qt, e sem catálogo instalado o
Qt fala inglês — num produto inteiramente em pt-BR.

**Consertado no mesmo lugar e pelo mesmo argumento do bloqueante**: o filtro que já visita todo
diálogo no `QEvent.Show` passou a pôr os botões padrão em português, lendo
`ui/strings.BOTOES_PADRAO` — puro, testável sem janela, indexado pelo **nome do enum** e não pelo
texto inglês (uma tabela `"Close" → "Fechar"` envelheceria com a versão do Qt e com o idioma da
máquina). Doze chamadas espalhadas teriam a mesma doença de sempre: a décima terceira nasceria em
inglês.

```
  depois:  botoes padrao: 12   EM INGLES: 0
  Procurar · Cancelar · Varrer · Cancelar · Fechar · Fechar · Fechar · Colar · Cancelar ·
  Abrir · Cancelar · Fechar
```

**Botão feito à mão sobrevive à tabela**, que é o mesmo contrato de `nomear_tudo` — o explícito
vence o derivado: `addButton(texto, papel)` devolve `NoButton` em `standardButton`, e é por isso
que o `Varrer` de `DialogoDeEscopo` e o `Colar` de `_JanelaDeColar` continuam dizendo o verbo. E
nenhum texto da tabela tem menos de três letras: `"OK"` tem duas, e um botão que chega ao leitor
de tela como `"OK"` é da família do `-` e do `+` do ciclo 1 — por isso `Ok → "Confirmar"`.

### Item 6 — a linha do Dataset a 4K · **corrigida: a tabela traz o número que a régua devolve**

Medido por mim, com `c5_vazios.py` do crítico do ciclo 5 sem alteração, sobre as capturas **deste
ciclo**:

| painel | 1920 claro | **3840 claro** |
|---|---|---|
| Revisão | 394,0 | **3 104,2** |
| Texto | 425,0 | **2 050,6** |
| **Dataset** | 370,3 | **1 905,3** |
| Estudo | 281,5 | **1 569,6** |
| Galeria | 224,0 | **1 550,0** |
| Resultado | 118,7 | **43,3** |

**O 1 905,3 é o que a régua devolve, e é o que está na tabela.** O 1 912,4 do relatório do ciclo 10
não reproduz em nenhuma das medições — nem na minha, nem na do crítico — e fica aqui, na nota,
como história: ele foi publicado porque estava escrito num ciclo anterior, e a lição é a que o
crítico escreveu — a tabela traz o que a régua devolve hoje, e a história vai para o rodapé.

Os doze números de 1920 batem à decimal com os dos dois ciclos anteriores.

### Item 7 — a marca da FEN só do lado direito · **aberto, declarado, de volta à lista**

`qt/rotulo.py:229` calcula `faixa = area.adjusted(area.width() - self._margem, 0, 0, 0)` e `:237`
desenha `RETICENCIA` nela: **há um só `drawText` e uma só faixa, e ela é sempre a da direita**. Com
o cursor no fim, o texto escondido está à esquerda e a marca está à direita. O arquivo não foi
tocado neste ciclo. **Ele estava fora da lista de abertos do ciclo 10 e volta a ela aqui.**

### Item 8 — `Motivo` ilegível a 1920 · **aberto, declarado, de volta à lista**

Reproduzido com `c6_aberto.py`, sem alteração:

```
  1920x1080: coluna 'Motivo' com 702 px -> 17 de 27 linhas nao cabem
  1366x768 : coluna 'Motivo' com 388 px -> 24 de 27 linhas nao cabem
  1280x800 :                            -> 25 de 27
```

Idêntico ao ciclo 9 e ao ciclo 11. **Ele também estava fora da lista de abertos e volta a ela.**

### Item 9 — a grade do ícone e o paginador · **parcial**: ver o item 3

A grade fecha em **20 de 24** grades nos seis arranjos. A tinta dos ícones continua entre **17,6 %
e 41,4 %** na grade de 16 px do cromo (amplitude relativa **80,8 %**), contra o alvo de ±20 %. Vale
a mesma explicação do item 3: é proporção de desenho, não de leiaute.

### Item 10 — a fronteira do portão de execução: ver o item 4 · **fechado**

### Item 11 — um separador só · **fechado**

O produto declarava `" · "` em dez lugares e escrevia `" | "` em quatro, **dois deles desenhados na
tela em toda pele e em toda largura**. Os quatro passaram para `" · "`:

```
  qt/painel_de_estudo.py    "Clique em uma peça para estudar. · vez: brancas"
  qt/painel_de_revisao.py   "... · 87% com sinal objetivo de erro"
  ui/pedido_de_treino.py    " · ".join(partes)
  ui/resumo_do_dataset.py   " · ".join(partes)
```

**A sexta regra não foi para um instrumento: foi para um teste** (`TestUmSeparadorSo`), que varre
`ui/` e `qt/` do tronco e reprova a outra grafia — e um segundo teste impede que a régua seja
satisfeita apagando os separadores. `cli/train.py` e `text/dataset.py` continuam com `" | "` de
propósito: ali é linha de log e de conjunto de dados, não interface.

### Item 12 — a Estudo e a Revisão redistribuírem a sobra acima de 1920 · **aberto, declarado**

**6 de 6 painéis acima de 200 kpx a 3840**, pior 3 104,2 kpx (Revisão). O Resultado faz o contrário
no mesmo produto (118,7 → 43,3 kpx), o que continua sendo a prova de que é escolha e não
fatalidade. Não mexi: redistribuir a sobra dos cinco painéis é desenho de leiaute de cada aba, e
não cabia neste ciclo ao lado do bloqueante.

### Item 13 — a terceira E/S de disco na thread da janela · **nomeada**

Medido nas execuções deste ciclo, o portão de bloqueio reprova com **7 operações acima do piso de
16 ms**, pior **223,5 ms** (mediana das três execuções internas: **149,1 ms**) em `abrir PDF`. A
pilha do pior nomeia `fz_run_display_list` (`painel_do_pdf.py`), `nt.stat` (`marcas.py:77
_marca_de`) e — **a que faltava nomear** — `sqlite3.Connection.execute` dentro de
`janela.py:_atualizar_abas`. São quatro caminhos de E/S de disco na thread da janela, e os quatro
estão nomeados agora. **Continua REPROVANDO**, e a parte desta frente no perfil é 1,5 %–2,0 %.

### Item 14 — os que continuam abertos, com os números de sempre

Declarados acima, sem atenuação, e mais os que a ordem de serviço nomeou à parte:

* **Os botões da fita sem rótulo**: **6 de 24**, nos dois modos e nos três arranjos da `fita`
  (medido em `c12_fita.py`: `6 botao(oes) sem rotulo`). São os seis comandos cujo rótulo era um
  glifo e cujo desenho o substituiu no ciclo 9 (`Comando.so_glifo`) — as duas lupas de zoom e as
  quatro setas do paginador. **A geometria deles fechou** (item 2: mesma altura, mesmo topo), e
  **o nome acessível deles nunca esteve em falta** — `nome_acessivel(acao)` dá `"Aumentar o zoom
  da página"` e o portão os aprova. O que falta é o rótulo desenhado, e não o pus porque o preço
  está medido: os seis rótulos por extenso passam por `quebrar_rotulo` (duas linhas) e alargam a
  fita, que a 1280 já quebra em duas filas — pagar altura por rótulo é exatamente o recurso que a
  S-228 protege. *Alvo: um rótulo curto de catálogo (`rotulo_curto`) para esses seis, medindo
  quantas filas a fita passa a ter a 1280.*
* **Última linha curta**: **6 de 18**, dois por pele, sempre a mesma frase (`onde parou.`, 7,2 %–7,3 %
  da medida). É o preço declarado de fechar as 6 órfãs no ciclo 10.
* **Tinta dos ícones**: **17,6 % a 41,4 %** na grade de 16 px, amplitude relativa **80,8 %**.
* **Poço à direita da paleta, piso da janela 1066×735, 2 pares com estados divergentes na Foco,
  barra determinada no dataset**: sem medição nova neste ciclo, e sem mudança no código que os
  produz.

### Item 15 — `bloqueio.py` para de reescrever a sessão: ver o item 5 · **fechado**

### Item 16 — higiene de arnês · **fechado**

* **`--saida` deixou de ter padrão nos seis portões que o tinham** (`bloqueio`, `contraste`,
  `execucao`, `progresso`, `quadros`, `teclado`). A constante `RELATORIOS`, que guardava o caminho
  de `benchmarks/reports/ui/` — a pasta do construtor —, **foi apagada dos seis módulos**: um
  caminho para a pasta de outro agente guardado num módulo de portão é a própria armadilha. Quem
  roda um portão diz onde quer o relatório. `teclado` aceita `--json` no lugar (é o que o laço de
  um arranjo por processo usa) e **recusa a chamada** quando não recebe nenhum dos dois.
  Cobrado por `TestOPadraoDeSaidaNaoApontaParaAPastaDoConstrutor`, nos seis.
* **O cabeçalho do portão de contraste deixou de dizer "nas duas peles"**: o que ele percorre são
  duas **polaridades de cromo** × duas **densidades**. A medição sempre esteve certa; o texto é que
  contava outra história. Cobrado por teste.

---

## §4 — Os portões, todos rodados

| portão | resultado |
|---|---|
| **Teclado + nome + papel, 6 arranjos + 13 diálogos** | **216/216/240/240/360/360 nas abas; 46 focáveis em 13 telas de diálogo por arranjo; 0 sem nome, 0 sem papel, 0 nome vazio, 0 fora do Tab. PASSOU em todos** |
| **Prova de vida dos diálogos (4 mutações)** | (0) 10 acusados sem a varredura · (a) só a `JanelaDeBusca` reprova · (b) o 13º diálogo derruba o portão · (c) a receita que some derruba o portão. `qt/*.py` idêntico antes e depois |
| **Censo de ícones, 6 arranjos** | **0 glifos em todos**; caixa única em **20 de 24** grades; amplitudes abertas 0×3, 0×11, 2×17 px |
| Contraste WCAG AA | **300 pares / 220 sob portão / 0 reprovados** nas duas polaridades × duas densidades; menor folga **3,27:1** e **3,03:1**. PASSOU |
| Estado morto | **3,66 / 3,27 / 3,66 : 1** nas três peles; mortos ≥ vivo mais fraco **1 de 26** em cada |
| Órfãs | **0 de 18**; 6 últimas linhas curtas (< 20 %), que é o preço declarado |
| Estado vazio na tela | **12 linhas por pele, 0 não desenhados, 0 duplicados** |
| Progresso | **8 indicadores, 13 operações de fundo, 0 invisíveis, nenhum defeito bloqueante** |
| **Execução (tronco vivo)** | **5 aberturas em 9 ações, 0 sem cobertura, 0 não atribuídas. PASSOU** |
| Execução, sabotagens | `sab_c9x` **8 de 8**, `sab_c10` **8 de 8**, **`sab_c12` 3 de 4** (era 1 de 4); 12 controles negativos calados |
| A janela sem torch | **7 de 7** na janela, **4 de 4** na rede. PASSOU |
| Vazio de painel | 10 de 12 acima de 200 kpx a 1920; **6 de 6 a 3840**, pior 3 104,2 kpx |
| **Bloqueio > 16 ms** | **REPROVOU**: 7 operações, pior **223,5 ms**, mediana **149,1 ms**. Parte desta frente: **2,0 %** do perfilado |
| Fita (geometria) | **1 altura e 1 topo por fila** nos seis arranjos; 5 de 5 cabeçalhos no pleno, 4 de 4 filetes no compacto |
| **Retrato dos 13 diálogos (régua nova)** | os doze `QDialog` fotografados pela primeira vez nesta frente; **7 de 12 botões padrão em inglês → 0** |

---

## §5 — Suítes

| suíte | resultado |
|---|---|
| `tests/unit/ui` (nossa, F9) | **198 passed** em 2,32 s — eram **161**; entraram **37** |
| **nossa, sem `tests/integration/test_packaging.py`** | **3 086 passed, 1 skipped, 0 failed** em 737,03 s — eram 3 049; entraram os 37 |
| **tronco inteiro** | **3 failed, 4 486 passed, 2 skipped, 4 536 subtests** em 296,50 s |
| `tests/test_field_eval.py` | **101 passed, 142 subtests, 0 failed** — era 1 failed |

**O tronco voltou a 3 reprovações, que é o alvo da ordem de serviço**, e ele tem **um passed a
mais** que o placar do ciclo 11 (4 486 contra 4 485) — é exatamente o `test_field_eval` que
fechou. As três que ficam **não são desta frente**, e digo qual módulo cada uma nomeia:

```
  test_docs::test_a_arvore_do_README_lista_todo_modulo_do_pacote
      -> desenho_de_diagrama.py, pdf_substituicao.py fora da árvore do README
  test_editor_model::SemTkinterTests::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter
      -> biblioteca.py, cortina.py, selecao_de_area.py, substituicao.py
  test_strings::AccentTests::test_no_ui_string_uses_an_unaccented_portuguese_word
      -> biblioteca.py ('cabecas'), substituicao.py ('pagina' x4), tokens.py ('SELECAO')
```

Nenhum desses seis módulos é meu, e conferi a atribuição **rodando as três com as minhas mudanças
guardadas** (`git stash`): as três reprovam do mesmo jeito sem elas.

**E uma quarta reprovou por minha causa, durante o ciclo, e está consertada**:
`test_packaging::TamanhoDaJanelaTests::test_a_janela_nao_volta_a_crescer` — ver §1.1. `qt/janela.py`
voltou às 1 883 linhas, sem baixar o corte do teste.

O pulo é o mesmo de sempre (`tests/unit/typeset/test_fonts.py:333`, WOFF2 sem o compressor
Brotli). **`0 failed` pela quarta execução independente**, e o número subiu exatamente pelos 37
testes que este ciclo escreveu.

**Nenhum teste foi afrouxado.** As três réguas afinadas neste ciclo (§1.4) vieram acompanhadas de
testes que repõem o defeito exato que criou cada regra, e os cinco defeitos que o produto tinha
foram consertados **no produto** e não na régua.

---

## §6 — Nota de procedimento

* **Conferi o destino de cada script antes de rodá-lo.** Os instrumentos `c10_*` que reusei
  (`c10_estado_morto`, `c10_orfas`, `c10_vazio_na_tela`, `c10_sem_torch`) não gravam nada —
  conferido por busca de `write_text`/`json.dump`/`.save(` antes de cada um. `c6_aberto.py` escreve
  o estado de medição dele numa pasta temporária, fora do repositório.
* **Nada foi escrito fora de `docs/quality/F9_REPORT_C12.md`, de `benchmarks/reports/ui/c12/`, de
  `src/caissa/ui/`, de `tests/unit/ui/` e dos arquivos do tronco em `qt/` e `ui/`** — com **duas**
  exceções declaradas, as duas do item de `test_field_eval`:
  1. os quatro `docs/metrics/*.json` do tronco, que são o objeto da remedição;
  2. a etiqueta `f9-c12-arvore-limpa` no repositório do tronco, que mantém alcançável o commit que
     os quatro relatórios citam como proveniência. A árvore de trabalho temporária foi removida.
* **`PYTHONDONTWRITEBYTECODE=1` em toda invocação.**
* **`data/janela.json` do tronco, medido e não afirmado.** Antes do portão de bloqueio:
  `sha256 77d24622…cd`. **Depois das três execuções dele: `77d24622…cd`, byte a byte** — que é o
  item 5, e é o mesmo hash que o crítico do ciclo 11 registrou ao restaurar o arquivo.
  **Mais tarde na sessão o arquivo mudou para `a8e53bd5…a1`, com `mtime` 21:07**, e digo o que
  sei e o que não sei: 21:07 cai dentro da primeira execução da suíte do tronco, que não é arnês
  desta frente; o conteúdo continua sendo uma sessão de uso normal (o mesmo `1937 Kemeri.pdf`,
  página 120, zoom 0,3055 que o arquivo já tinha); a **segunda** execução da suíte, às 21:23, não
  o reescreveu; e **nenhum módulo do arnês desta frente constrói `JanelaPrincipal` sem
  `caminho_do_estado`** — isso agora é teste, não promessa. Não consigo atribuir a mudança a nada
  que eu tenha rodado, e não consigo desfazê-la porque só tenho o hash do estado anterior, não os
  bytes. Fica registrado com o número, que é o que a carta pede de quem não pode provar.
* **A prova de vida cria e apaga um arquivo novo em `qt/`** (`_sonda_c12.py`) e **não edita nenhum
  arquivo existente**; o SHA-256 da pasta inteira é conferido antes e depois, e bateu.
* **Um defeito de instrumento do crítico, para quem vier:** `c11_dialogos.py` e
  `c11_dialogos_prova.py` terminam com *segmentation fault* **depois** de imprimir o resultado
  inteiro. É a fila de `DeferredDelete` do Qt que o arnês desta frente documenta em
  `teclado._descartar` — os dois instrumentos fecham os diálogos sem destruí-los. **Não é
  consequência deste ciclo**: conferido rodando os mesmos instrumentos com
  `vigiar_dialogos` desligado, e o aborto é o mesmo. Os números que eles imprimem são válidos.

---

## §7 — Como reproduzir

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=<tronco>\src;<suite>\src
set C12=benchmarks\reports\ui\c12
set PY=..\ChessVisionOFF_Puro\.venv\Scripts\python.exe

:: O BLOQUEANTE
%PY% -m caissa.ui.audit.teclado --pdf "...\1937 Kemeri.pdf" --saida %C12%\gate_teclado
   :: 6 arranjos x (6 abas + 13 dialogos); 216/240/360 + 46; PASSOU em todos
%PY% %C12%\c12_prova_de_vida_dos_dialogos.py     :: 4 mutacoes; sha de qt/*.py identico
%PY% benchmarks\reports\critique\ui\c11\c11_dialogos_prova.py   :: do critico: antes=0 (era 11)

:: os itens
%PY% %C12%\c12_fita.py                  :: modo, cabecalhos, filetes, topos e alturas
%PY% %C12%\c12_icones_da_janela.py      :: 6 arranjos; 0 glifos; caixa unica em 20 de 24
%PY% %C12%\c12_retrato_dos_dialogos.py [pele]   :: fotografa os 13 dialogos
%PY% %C12%\c12_zoom.py <png> x0 y0 x1 y1 [fator] [nome]
%PY% -m caissa.ui.audit.execucao --sabotagem %C12%\sab_c12 --saida %C12%\gates   :: 3 de 4

:: os portoes (--saida agora e' OBRIGATORIO em todos)
%PY% -m caissa.ui.audit.contraste --saida %C12%\gates
%PY% -m caissa.ui.audit.progresso --saida %C12%\gates
%PY% -m caissa.ui.audit.execucao  --pdf "..." --saida %C12%\gates
%PY% -m caissa.ui.audit.bloqueio  --pdf "..." --saida %C12%\gates
%PY% -m caissa.ui.audit.capture   --saida %C12%\capturas --marca c12 --pdf "..."

:: a arvore limpa do test_field_eval (nao toca em HEAD, indice nem ramo)
set GIT_INDEX_FILE=%TEMP%\idx
git read-tree HEAD & git add -u & git write-tree
git commit-tree <tree> -p HEAD -m "..."     &  git worktree add --detach <pasta> <commit>
<tronco>\.venv\Scripts\python.exe -m chess_diagram_ocr.cli.field --model models/<m>.pt --json <fora>

:: suites
.venv\Scripts\python.exe -m pytest tests\unit\ui -q          :: 198 passed
.venv\Scripts\python.exe -m pytest tests -q --ignore=tests\integration\test_packaging.py
<tronco>\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly
<tronco>\.venv\Scripts\python.exe -m pytest tests\test_field_eval.py -q -p no:randomly
```

Artefatos deste ciclo, todos em `benchmarks/reports/ui/c12/`: `gate_teclado/` e `gates/` (os JSON
dos portões), `capturas/` (72 PNG), `dialogos/` (13 PNG, os diálogos fotografados pela primeira
vez), `sab_c12/`, os instrumentos `c12_*.py` e os recortes `z12_*.png`.
