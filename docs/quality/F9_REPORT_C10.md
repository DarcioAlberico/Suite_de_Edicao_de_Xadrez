# F9 — Interface, relatório do ciclo 10

Responde ao `docs/quality/F9_CRITIQUE_C9.md`. Todo número abaixo saiu de um comando rodado neste
ciclo; onde um número piorou, ele está aqui com o mesmo destaque dos que melhoraram.

## Nota de autoria — o ciclo teve dois agentes, e isto diz quem fez o quê

O primeiro agente foi interrompido por limite de taxa esperando a **segunda** execução da nossa
suíte confirmar a primeira. **Os itens 1 a 8 são dele**: o produto, os portões, os instrumentos,
as duas provas de vida e os números que este documento publica em cada seção.

O segundo agente fez quatro coisas, e nenhuma delas reescreve um número do primeiro:

1. **Reproduziu os portões do zero**, sem alterar uma linha, para conferir se o que está em disco
   devolve o que este relatório afirma. Os números batem, e a lista está no §Reprodução
   independente, no fim.
2. **Fechou o item 9** — a pendência de empacotamento (`packaging/pendencias/0001-...patch`), que
   não vem da crítica do ciclo 9 —, consertou a reprovação que ela causou em
   `tests/test_checkpoint.py` **sem tocar no teste**, e declarou aberta a que ela causou em
   `tests/test_field_eval.py` com o número e o motivo (§9.4).
3. **Olhou as 72 capturas** com os próprios olhos, nas três peles e nos quatro tamanhos, incluindo
   4K — e o que viu está no §Reprodução independente e no §O que só o olho achou.
4. **Rodou as seis execuções de suíte** que faltavam (duas do tronco, duas da nossa inteira e duas
   da nossa sem o arquivo que lê artefato de outro agente) e preencheu o §Suítes, que era a única
   lacuna que o primeiro agente deixou por escrito. **As duas que fecham a pergunta de determinismo
   batem à segunda decimal**, e reproduzem o `3049 passed, 1 skipped, 0 failed` que ele mediu antes
   de cair.

Onde uma seção diz "eu", é o primeiro agente. As seções §9, §Reprodução independente e §Suítes
são do segundo, e dizem isso.

**O bloqueante era um, e ele está fechado nas três metades que o crítico exigiu** — o glifo que
sai, o nome acessível que entra, e os portões percorrendo `ui/pele.PELES`. O portão de teclado
devolve **PASSOU nas três peles** (216 / 240 / 360 focáveis, `0 sem nome, 0 sem papel, 0 nome
vazio de sentido, 0 fora do Tab`), e o censo de ícones devolve **`GLIFOS DE TEXTO: 0` nas três**.

**A prova de vida que o crítico pediu achou um furo no meu próprio portão, e ele está no §1.4.**
Apaguei o `setAccessibleName` da fita — o defeito do ciclo 9 reposto — e o portão continuou
verde: sem nome próprio a cascata cai no `text()`, e o texto de um botão da fita é
`quebrar_rotulo("Abrir PDF")` = **`"Abrir\nPDF"`**, que tem letras, é único e não é prosa. **E não
bate com `"Abrir PDF"`** — era essa quebra de linha que escondia, desde sempre, os onze nomes da
fita que colidem com os da barra do visor. Com o motivo novo (`quebra de linha no nome`), a mesma
sabotagem devolve **90 controles acusados** na pele `fita`.

---

## Resumo

| # | item | número medido | veredito |
|---|---|---|---|
| **1 (bloqueante)** | glifo + nome acessível na `fita`, portões nas três peles | teclado **PASSOU** nas 3 (era 0 / 2 / 36 defeitos); censo **0 glifos** nas 3 (era 6 na fita) | **FECHADO**, com prova de vida nos dois sentidos |
| 2 | detector de thread: 8 de 8 formas novas escapavam | portão de **execução** novo: **8/8** do crítico e **8/8** minhas, 4+5 controles negativos calados | **FECHADO** por troca de forma |
| 3 | `determinado` nunca diverge de `passa_total`; um tique apaga o portão | faixa medida **por operação**, depois de a fila assentar. Sabotagem "nunca troca de modo": **4 bloqueantes, 4 divergências** (era 0) | **FECHADO** |
| 4 | estado morto custa 1,88:1 na pele Foco | vivo↔morto **3,66:1** (clássica/fita) e **3,27:1** (Foco); mortos mais legíveis que o vivo mais fraco: **22/22 → 1/26** | **FECHADO**, com a conta que ele custou |
| 5 | 8 de 54 parágrafos com órfã | mesma régua antes e depois: **6 de 18 → 0 de 18** | **FECHADO**; linha curta (<20 %) fica **ABERTA** com número |
| 6 | 4K nunca foi rodado | `capture.TAMANHOS` ganha 3840×2160: **72 capturas** (3 peles × 4 tamanhos × 6 abas), e o pior vazio a 4K **não é o da Estudo** | **MEDIDO**; o desenho a 4K fica **ABERTO** com número |
| 7 | o censo de ícones não vê botão com ícone **e** texto | filtro passa a `if tem_icone`; e o lado do cromo deixa de ser o literal `16` — na `fita` ele é **11 px** | **FECHADO** |
| 8 | `nomear_o_que_o_cromo_nao_desenha` não pergunta `isVisible()` | passa a perguntar `isVisibleTo(cromo)`; 36 linhas de estado vazio, **0 não desenhados, 0 duplicados** | **FECHADO** |
| 9 | a janela do tronco não abre sem torch (pendência do empacotamento) | 4 arestas cortadas: **7 de 7** módulos da janela importam com torch bloqueado, e os **4** da rede continuam exigindo | **FECHADO**; a impressão de 4 relatórios de campo fica **ABERTA** (§9.4) |

---

## Item 1 — o bloqueante. **FECHADO**

### 1.1 O que estava errado, reproduzido antes de tocar em nada

O portão de teclado rodado nas três peles, sem alterar uma linha:

```
  CVOFF_SKIN=classica   216 focaveis   0 sem sentido   PASSOU
  CVOFF_SKIN=foco       240 focaveis   2 sem sentido   REPROVOU
  CVOFF_SKIN=fita       360 focaveis  36 sem sentido   REPROVOU
```

Os 36 da `fita` são seis por aba, nas seis abas, e os seis são os comandos cujo rótulo de botão é
um glifo puro. O catálogo os nomeia sozinho:

```
  zoom_menos       no_botao='-'   icone='zoom_menos'         no_leitor='Diminuir o zoom da página'
  zoom_mais        no_botao='+'   icone='zoom_mais'          no_leitor='Aumentar o zoom da página'
  lance_anterior   no_botao='◀'   icone='diagrama_anterior'  no_leitor='Lance anterior'
  proximo_lance    no_botao='▶'   icone='proximo_diagrama'   no_leitor='Próximo lance'
  inicio_da_linha  no_botao='|◀'  icone='inicio_da_linha'    no_leitor='Início da linha'
  fim_da_linha     no_botao='▶|'  icone='fim_da_linha'       no_leitor='Fim da linha'
```

Os 2 da `foco` são `"Próximo diagrama"` duas vezes na aba Galeria — a pílula do cromo e o botão do
paginador do painel, o mesmo comando desenhado nos dois lugares de propósito.

### 1.2 O conserto de produto

**`ui/comandos.Comando.so_glifo`** — a regra mora no catálogo, e não em cada cromo. *"Sem letra"* e
não uma lista de glifos, que é a mesma régua de `audit/teclado.nome_vazio_de_sentido`: uma lista
teria de ser lembrada no dia em que alguém escrevesse `«` num rótulo curto.

**`qt/fita.py::_botao`** passa por `qt/icones.vestir` — a regra que já existia e cujo docstring diz
*"põe o desenho **e apaga o glifo**"* — com `manter_texto=not registro.so_glifo`; e chama
`setAccessibleName(comandos.nome_acessivel(acao))`, que é a linha que `qt/painel_do_pdf._botao` tem
desde o ciclo 2.

**`qt/fila.py::_pilula`** recebe as duas mesmas linhas. Nenhum comando em destaque tem rótulo de
glifo hoje, então o número da pele Foco não muda com isso — **o que muda é que ele deixa de
depender disso**, e é por isso que `test_qt_fila.py` monta a pílula de um comando de glifo do
catálogo pelo caminho da fila e cobra as duas propriedades.

**A porta de trás está fechada junto**: `Fita._alternado` escrevia o rótulo de um comando que
alterna, e `setText` num botão vestido de ícone reporia o glifo — escrito pelo **estado**, onde
nenhum censo de montagem o procura. Nenhum dos seis alterna hoje; a guarda existe para o dia em que
um passar a alternar.

### 1.3 O conserto que o `setAccessibleName` obrigou, e ele não estava previsto

Com o nome acessível na fita, **os 36 `sem letras` viraram 0 — e apareceram 22 a 30 `repetido na
aba` por aba**, porque a fita repete onze comandos da barra do visor e os dois lados passaram a
anunciar a mesma palavra. Medido, com a cadeia de contêineres de cada lado
(`benchmarks/reports/ui/c10/c10_repetidos.py`):

```
  'Abrir PDF'
      QToolButton   em (nenhum conteiner nomeado)     <- a fita
      QPushButton   em Livro [QWidget]                <- a barra do visor
  'Ajustar à largura' / 'Ajustar à página' / 'Aumentar o zoom' / 'Diminuir o zoom'
      QToolButton   em (nenhum conteiner nomeado)
      QPushButton   em Zoom [QWidget]
  ... 11 nomes na aba Resultado, 15 na Estudo
```

**Todas as colisões são cromo × painel, e o lado do painel está sempre dentro de um contêiner
nomeado.** O modelo é do próprio produto e está escrito no docstring de
`qt/painel_do_pdf._bloco` desde o ciclo 2: *"o nome do bloco é o que um leitor de tela anuncia ao
entrar nele; sem ele a pessoa ouve doze botões seguidos sem saber onde um grupo acaba"*. **O cromo
não nomeava os grupos dele, e o portão só lia a segunda metade do anúncio.**

Duas linhas de produto e uma de portão:

* `qt/fita.py::_grupo` → `moldura.setAccessibleName(grupo.rotulo)` (a mesma linha de `_bloco`);
* `qt/fila.py` → `self.setAccessibleName("Ações em destaque")`, que é o nome que a S-223 dá à fila;
* `caissa/ui/audit/teclado.Controle.grupo` + `nome_qualificado()` → *"repetido na aba"* passa a
  comparar **o anúncio inteiro**, `"Navegar: Página anterior"`.

**Isto cobra do produto uma coisa a mais, e não a menos.** Dois controles com o mesmo nome dentro
do **mesmo** grupo continuam reprovando; um controle sem grupo nomeado continua sendo comparado
pelo nome cru; e a fita só passa porque agora **nomeia os grupos dela**. Os quatro testes que
seguram os dois lados estão em `tests/unit/ui/test_medicao.TestNomeQualificado`, incluindo
`test_dois_iguais_no_mesmo_grupo_continuam_reprovando` (os três `"Escolha"` do ciclo 2).

### 1.4 A prova de vida — e o furo que ela achou no meu portão

`benchmarks/reports/ui/c10/c10_prova_de_vida.py` copia `qt/fita.py`, sabota, roda os dois portões e
restaura o arquivo **conferindo SHA-256 byte a byte** (o script recusa terminar se o hash não
bater). É a disciplina com que o crítico do ciclo 9 envenenou e restaurou
`data/app_tkinter_state.json`.

**Primeira execução, e ela reprovou a mim:**

```
  SABOTAGEM: sem nome acessivel      teclado=PASSOU  <<< o portao NAO reprovou
  SABOTAGEM: glifo ao lado do desenho  censo=REPROVOU (6 glifos na fita)
```

O motivo está no cabeçalho deste relatório: sem `accessibleName`, a cascata cai no `text()`, e o
texto de um botão da fita é `"Abrir\nPDF"` — **com uma quebra de linha no meio**. Aquilo tem
letras, é único na aba, não é o valor do controle e não é prosa; e não bate com `"Abrir PDF"`, então
nem repetido ficava. **Era esse mascaramento que escondia as onze duplicações do §1.3.**

`MOTIVOS_DE_NOME_VAZIO` ganhou o sexto motivo — **`quebra de linha no nome`** —, porque uma quebra
de linha num nome acessível é o leiaute vazando para o anúncio: ela existe porque o botão tem duas
linhas de altura, e um leitor de tela lê *"Abrir, PDF"* com uma pausa no meio.

Com o motivo, a prova de vida fecha nos dois sentidos:

```
  SEM SABOTAGEM                        teclado=PASSOU   censo=PASSOU (0 glifos nas 3 peles)
  SABOTAGEM sem nome acessivel         teclado=REPROVOU -- fita: 15 por aba x 6 abas = 90 acusados
  SABOTAGEM glifo ao lado do desenho   censo=REPROVOU   -- fita: 6 glifos
  qt/fita.py restaurado, sha256 confere: sim
```

### 1.5 O placar, nas três peles

```
  classica    216 focáveis   0 sem nome   0 sem papel   0 nome vazio   0 fora do Tab   PASSOU
  foco        240 focáveis   0 sem nome   0 sem papel   0 nome vazio   0 fora do Tab   PASSOU
  fita        360 focáveis   0 sem nome   0 sem papel   0 nome vazio   0 fora do Tab   PASSOU
  Veredito de TODAS as peles: PASSOU
```

**O `for` está no portão, e a lista vem do produto.** `teclado.peles_registradas()` lê
`ui/pele.PELES`; uma pele nova entra no portão no mesmo commit em que entra no menu, e
`tests/unit/ui/test_medicao.TestTodasAsPeles` falha no dia em que `capture.PELES` divergir dessa
lista.

**Uma pele por processo, e isso foi medido e não escolhido.** A primeira forma do laço montava as
três janelas no mesmo processo e a terceira **abortava o interpretador** no meio da aba Texto, sem
traceback — a janela anterior morria por coleta de lixo com `DeferredDelete` pendentes no Qt.
Destruir à mão (`sendPostedEvents(..., DeferredDelete)`, como `tests/qt_app.descartar`) adiou o
aborto sem o apagar. Um subprocesso por pele também é a medição mais limpa: nenhuma pele herda o
cache de ícone nem os seguidores de comando da anterior. **E um subprocesso que morre não vira uma
pele que some**: sem o JSON dela o método levanta, nomeando a pele.

### 1.6 O que o olho vê

`benchmarks/reports/ui/c10/z_fita_ribbon_esq.png` e `z_fita_ribbon_dir.png`, a 3×: os quatro botões
de navegação da fita desenham **só o triângulo**, e os dois de zoom **só a lupa**. O `◀` de 5×3 px
que o ciclo 7 mediu e o ciclo 8 apagou em todo lugar menos ali não está mais na tela.

**E o que eu vi de ruim, com o número:** dos 24 botões da fita, **6 ficaram só-de-ícone e 18
continuam com rótulo**. Nos quatro de navegação isso é o certo -- eles nunca tiveram palavra --,
mas os **dois de zoom** ficam sem rótulo ao lado de `Ajustar à página` e `Ajustar à largura`, e o
glifo `-`/`+` era o que os fazia parecer rotulados. É a mesma decisão que `qt/painel_do_pdf` toma para esses dois comandos desde o ciclo 2
(`so_icone=True`), e o nome por extenso continua na dica e no `accessibleName`; mas na fita, que é
uma pele de "ícone grande **com** rótulo", eles agora são a exceção visível. Fica **declarado**, e
não corrigido: dar-lhes rótulo exige trocar `rotulo_curto` no catálogo, o que mexe em
`_e_outro_nome` e na barra do visor — não cabia ao lado do bloqueante.

---

## Item 2 — o detector de thread vira portão de **execução**. **FECHADO por troca de forma**

### 2.1 Por que a forma mudou

A história da régua de AST, ciclo a ciclo, é uma corrida perdida:

| rodada | sabotagem | pegava |
|---|---|---|
| ciclo 5 (crítico) | 6 formas | 1 de 6 → depois 6 de 6 |
| ciclo 7 (crítico) | 8 formas | 1 de 8 → depois 8 de 8 |
| ciclo 8 (construtor) | 8 formas | 1 de 8 → depois 8 de 8 |
| **ciclo 9 (crítico)** | **8 formas novas** | **0 de 8** |

`caissa/ui/audit/execucao.py` é o portão novo, e ele observa **duas** coisas:

1. **Os pontos de abertura**, interceptados: `threading.Thread.start`, `QThread.start`,
   `QThreadPool.start`/`tryStart`, `QProcess.start`/`startDetached`, `subprocess.Popen`,
   `os.startfile`. Cada interceptação guarda a **origem** — o quadro de pilha mais interno que não
   é da biblioteca-padrão nem do próprio arnês. É o que faz `executor.submit(...)` ser atribuído a
   **quem o chamou**, e não a `concurrent/futures/thread.py`.
2. **`threading.enumerate()` antes e depois**, que é a rede: qualquer thread de Python que nasça e
   que a lista de (1) **não** explique sai como `NAO ATRIBUIDA`, com nome e `target`. **Uma forma
   nova de abrir thread não escapa do portão — ela escapa da *atribuição*, e o portão diz isso.**
   Era exatamente isso que a AST não conseguia: o que ela não conhecia, ela não reportava.

**O que ele ainda não vê, dito sem atenuar:** trabalho aberto por biblioteca nativa que não passe
por nenhum dos oito pontos e não crie thread de Python. É uma fronteira de mecanismo, não uma lista
de padrões que envelhece: para atravessá-la é preciso sair do Python.

### 2.2 As oito do crítico — e uma descoberta sobre elas

**A cópia fiel de `sab_c9` não importa neste ambiente:**

```
  MODULO NAO EXECUTAVEL  sabotador_c9.py:
      ImportError: cannot import name 'QtConcurrent' from 'PyQt6.QtCore'
```

Conferido: o nome não existe em `QtCore.pyd` deste venv (PyQt6 não empacota `QtConcurrent`, como
também não empacota `QAccessible`). **A forma (f) daquela sabotagem nunca foi executável nesta
máquina** — ela é sintaxe válida que a AST lê e que nenhum portão de execução poderia observar,
porque ela não corre. O portão publica isso em vez de fingir que mediu.

`benchmarks/reports/ui/c10/sab_c9x/` é a transcrição executável das oito, com **uma** linha trocada
(a forma (f) vira `QThreadPool.globalInstance().start(QRunnable)`, que é o que `QtConcurrent.run`
faz por baixo), e o motivo está no docstring do arquivo:

```
  forma  a_classe_devolvida        PEGA  threading.Thread.start   sabotador_c9x.py::a_classe_devolvida
  forma  b_walrus                  PEGA  threading.Thread.start   sabotador_c9x.py::b_walrus
  forma  c_desempacotado           PEGA  threading.Thread.start   sabotador_c9x.py::c_desempacotado
  forma  d_campo_anotado           PEGA  threading.Thread.start   sabotador_c9x.py::d_campo_anotado
  forma  e_processo_destacado      PEGA  QProcess.startDetached   sabotador_c9x.py::e_processo_destacado
  forma  f_pool_global_do_qt       PEGA  QThreadPool.start        sabotador_c9x.py::f_pool_global_do_qt
  forma  g_decorada                PEGA  threading.Thread.start   ajudante_de_fundo.py::dentro
  forma  h_subclasse_dinamica      PEGA  threading.Thread.start   sabotador_c9x.py::h_subclasse_dinamica
  controle negativo  n1..n4        calada (4 de 4)
  formas pegas: 8 de 8   -> PASSOU
```

### 2.3 As oito minhas (`sab_c10/`), escolhidas para atacar a **execução**

Nenhuma está nas quarenta anteriores. Três escondem a construção onde nenhuma AST alcança, duas
atacam o **instante**, duas a **atribuição**, e uma é a `Timer`, que é `Thread` sem parecer uma:

```
  forma  a_temporizador             PEGA  threading.Thread.start   ::a_temporizador
  forma  b_exec_de_string           PEGA  threading.Thread.start   ::b_exec_de_string
  forma  c_getattr_no_start         PEGA  threading.Thread.start   ::c_getattr_no_start
  forma  d_run_anonimo              PEGA  threading.Thread.start   ::d_run_anonimo
  forma  e_um_tique_depois          PEGA  threading.Thread.start   ::<lambda>
  forma  f_por_sinal                PEGA  threading.Thread.start   ::_quando_o_sinal_chega
  forma  g_thread_dentro_de_thread  PEGA  threading.Thread.start   ::_abre_outra, ::g_thread_dentro_de_thread
  forma  h_pool_disfarcado          PEGA  subprocess.Popen + threading.Thread.start  ::h_pool_disfarcado
  controle negativo  n1..n5         calada (5 de 5)
  formas pegas: 8 de 8   -> PASSOU
```

`e_um_tique_depois` e `f_por_sinal` são as que provam que o instante não escapa: a thread nasce
**depois** da chamada, num tique de `QTimer.singleShot` e num slot de sinal, e o portão gira a fila
de eventos e espera `TEMPO_DE_ASSENTAR_S` antes de fechar a conta.

### 2.4 O tronco real

Nove ações da janela viva (abrir o livro, três páginas, as seis abas):

```
  abrir o livro          2 aberturas  1 registros  0 sem cobertura  0 nao atribuidas
      QThread.start   marcas.py::pedir:169             coberta
      QThread.start   trabalho.py::_comecar:130        coberta
  ir para a pagina 41    1 abertura   0 registros  0 sem cobertura
      QThread.start   trabalho.py::_comecar:130        coberta
  ir para a pagina 121   1 abertura   0 registros  0 sem cobertura
      QThread.start   trabalho.py::_comecar:130        coberta
  abrir a aba Dataset    1 abertura   1 registro   0 sem cobertura
      QThread.start   painel_do_dataset.py::_reler_agora:428   coberta
  as outras cinco acoes  0 aberturas
  Aberturas sem cobertura: 0   Threads nao atribuidas: 0   Veredito: PASSOU
```

**Cinco aberturas em nove ações**, e as três origens são as que a tabela declara ou que registram.

**Uma confissão de teste, e ela é sobre este portão.** A metade de janela dele (`auditar`) não é
coberta pelos meus 12 testes -- eles medem a parte pura, porque a nossa venv não tem PyQt6 --, e
uma linha faltando (`import tempfile`) passou por eles e morreu na primeira execução com
`NameError`. O teste de arquitetura importa o módulo; ele não o **roda**. Foi o portão rodado que
achou, que é o argumento inteiro deste item: uma coisa que corre é observável, e uma que não
corre não é.

A regra de cobertura é declarada: a origem `(arquivo, função)` está em `ui/busy.FORA_DO_REGISTRO`,
ou houve um `register(...)` **do mesmo arquivo** na mesma ação — e o registro é interceptado com a
mesma resolução de origem, então "o mesmo arquivo" é medido e não suposto.

### 2.5 A régua de AST **continua**, e as catracas continuam

O portão de execução responde *"o que abriu trabalho enquanto isto correu"*; o de AST responde
*"o que existe no código"*, e é ele que ainda alimenta a tabela de operações de fundo do relatório
de progresso. Rodados sem alteração:

```
  sabotagem do critico do ciclo 5 : 6 de 6 formas   (+1 defeito historico da propria arvore)
  sabotagem do critico do ciclo 7 : 10             (as 8 formas + 2 do __init__)
  sabotagem C8 (construtor)       : 8 de 8
  sabotagem do critico do ciclo 9 : 1              (0 de 8 formas -- e por isso o portao mudou)
  TRONCO REAL                     : 13 operacoes de fundo em qt/, 0 invisiveis
```

### 2.6 A régua gêmea, na suíte do tronco

O alvo do §4.1 diz *"a **suíte Qt** conta `threading.enumerate()` antes e depois de cada ação"*, e a
lição do ciclo 5 é que **o teste e o portão têm de mudar juntos** -- foi assim que a régua de AST
ganhou a sabotagem C5 do lado do tronco. `tests/test_busy.PortaoDeExecucaoTests` é a gêmea deste
ciclo, seis testes:

```
  test_nenhuma_abertura_da_janela_fica_sem_cobertura     a janela viva, aba por aba
  test_a_regua_acusa_uma_thread_crua_de_arquivo_nao_declarado    <- a prova de vida
  test_a_regua_fica_calada_quando_o_mesmo_arquivo_registra
  test_a_regua_fica_calada_quando_nada_abre_trabalho
  test_o_vigia_desfaz_o_remendo_ao_sair
  test_o_qthread_restaurado_continua_chamavel                    <- a guarda do §2.7
  test_um_bloco_que_levanta_tambem_desfaz
```

**A primeira forma dela falhou, e o defeito era da régua e não do produto.** Eu tinha copiado do
arnês a ideia de "pular os quadros de pilha do próprio instrumento **por caminho**" -- e no tronco
o instrumento e quem o chama moram no **mesmo arquivo**, então pular o arquivo apagava a resposta:
a prova de vida devolvia `(desconhecido)::(desconhecido)` em vez do nome do teste. Hoje os quadros
do vigia são **contados** e não filtrados por caminho, e o motivo está escrito na função.

### 2.7 E a régua gêmea achou um defeito no portão do arnês — este é o item

**A suíte do tronco foi de 3 reprovações para 26 quando esta classe entrou.** Vinte e três testes
que passavam começaram a falhar, e três deles com uma mensagem que nomeia a causa:

```
  tests/test_qt_trabalho.py::DeteccaoDeFundoTests  (3)
  tests/test_qt_painel_do_dataset.py::PainelTests  (3)
      TypeError: start(self, priority: QThread.Priority = QThread.InheritPriority):
                 first argument of unbound method must have type 'QThread'
```

**O vigia restaurava `QThread.start` com o objeto errado.** Para uma classe do sip,
`getattr(QThread, "start")` devolve um `builtin_function_or_method` **desligado da classe**;
devolvê-lo por `setattr` deixa `QThread.start` com algo que já não sabe se ligar à instância, e a
próxima chamada morre. Quem restaura de verdade é `QThread.__dict__["start"]`, o
`sip.methoddescriptor`. Conferido no interpretador antes de consertar.

**E o defeito estava também no portão do arnês, onde nada o teria pego.** Lá cada execução é um
processo, e o vigia é montado e desfeito nove vezes seguidas dentro dele -- então, a partir da
segunda ação, `QThread.start` já era o objeto quebrado. É por isso que a passada anterior contou
**4 aberturas** e a de agora conta **5**: a abertura da página 121 morria em silêncio dentro do
`try` que o portão põe em volta de cada ação.

**É exatamente o argumento da régua gêmea, e foi ela que cobrou.** O portão sozinho nunca acusaria:
ele mede o produto, e o que estava quebrado era ele. Um teste que roda no meio de quatro mil e
quinhentos outros, no mesmo processo, acusou em uma execução. O conserto está nos dois
`_remendar`, com o motivo escrito, e `test_o_qthread_restaurado_continua_chamavel` é a guarda.

---

## Item 3 — `determinado` medido **por operação**. **FECHADO**

### 3.1 O que estava errado

`faixas_medidas` media a faixa **exatamente duas vezes** (`total=289` e `total=0`) e resolvia
`determinado` por consulta a esse par, com chave `passa_total`. O crítico mediu a consequência:
*"7 registros; 0 em que `passa_total` e `determinado` divergem"* — a coluna publicada como medida
carregava a mesma informação que a coluna lida do código. E um tique a apagava.

### 3.2 O conserto

`faixa_por_operacao` mede num rodapé novo, com o total daquela operação, e **só lê depois de
`ASSENTAR_MS = 90` de fila girando** — 90 ms é o dobro do `singleShot(40)` da sabotagem, mais folga.
`determinado_medido` exige **duas** coisas: a faixa ser determinada **e diferir** da faixa que a
mesma barra tem sob uma ocupação indeterminada. A evidência publica as duas:

```
  faixa medida no rodape vivo com esta ocupacao: min=0 max=100, repouso min=0 max=0
      -> DETERMINADA (a barra TROCOU de modo)
```

### 3.3 A prova de vida (`c10_faixa_tardia.py`, com backup e SHA-256)

```
  === sem sabotagem ===                      registros=7  bloqueantes=0  divergencias=0
  === um tique de atraso (singleShot 40 ms) ===  registros=7  bloqueantes=0  divergencias=0
  === nunca troca de modo ===                registros=7  bloqueantes=4  divergencias=4
        treino do modelo:        total_conhecido=True determinado=False
        exportação para PGN:     total_conhecido=True determinado=False
        varredura do livro:      total_conhecido=True determinado=False
        detecção de duplicatas:  total_conhecido=True determinado=False
  qt/rodape.py restaurado, sha256 confere: sim
```

**O tique não engana mais o portão, e a barra que não troca de modo o faz acusar quatro operações.**

### 3.4 A heurística de contagem: uma metade fechada, a outra declarada

`_numero_calculado_na_mesma_funcao` passa a seguir a cadeia de atribuição **por aritmética**
(`PROFUNDIDADE_DA_CADEIA = 3`). Rodado contra `sab_c9_prog` do crítico, sem alterar a árvore dele:

```
  p1  montante = self.contagem_de_amostras()          ACUSA  ok
  p2  k = self.contagem_de_amostras()                 ACUSA  ok
  p3  detail f"{len(self.linhas())} linha(s)"         ACUSA  ok
  p4  parcial = ...; restante = parcial - 1           ACUSA  ok   <<< era o que ESCAPAVA
  n1  motor = self._motor (atributo lido)             calado ok
  n3, n4                                              calados ok
  n2  nome = self.nome_do_livro() (devolve STRING)    ACUSA  <<< FALSO POSITIVO, ABERTO
```

**4 de 4 positivos (era 3 de 4); 3 de 4 negativos calados (inalterado).**

**O falso positivo fica aberto, e digo por quê sem atenuar.** `nome = self.nome_do_livro()` e
`quantas = self.contagem_de_amostras()` têm **a mesma forma** na AST; separá-las exige tipos ou
execução. A regra que as separaria por nome de função é exatamente a que o ciclo 8 tirou daqui, e
ela custou *"renomeie a variável e o veredito inverte"*. O custo do falso positivo é uma
reprovação a mais numa operação que não tem total; o do falso negativo é uma barra andando ao lado
de um número. Escolhi errar para o lado que reprova.

---

## Item 4 — o estado morto passa a custar 3,0:1. **FECHADO**

### 4.1 A conta, e o que ela custou

`tokens.TEXTO_MORTO` é papel novo. O estado morto usava `TEXTO_SECUNDARIO`, que responde a outra
pergunta (*"isto é apoio"*, e não *"isto não responde"*); enquanto compartilhavam valor, mexer num
mexia no outro.

| pele | vivo ↔ morto | morto ↔ superfície |
|---|---|---|
| clássica / fita (`#555555` → **`#666666`**) | 2,82:1 → **3,66:1** | 6,54:1 → 5,04:1 |
| Foco (`#a7adb6` → **`#7a818b`**) | **1,88:1 → 3,27:1** | 7,14:1 → 4,10:1 |

**Com o cromo escuro as duas exigências são incompatíveis por uma casa decimal:** `morto ≥ 4,5:1
contra a superfície` pede luminância ≥ 0,2362 e `vivo↔morto ≥ 3,0:1` pede ≤ 0,2333. Escolhi o
segundo, e o motivo é da própria WCAG: **1.4.3 isenta explicitamente o texto de componente
inativo** do piso de 4,5, e não isenta ninguém de dizer que o controle está desligado. Os dois
números estão publicados, e a escolha está escrita no docstring de `tokens.TEXTO_MORTO`.

### 4.2 Medido na tinta desenhada, nas três peles

`c10_estado_morto.py` mede a tinta no `grab()` de cada botão — e não na paleta, **e a diferença
custou uma descoberta** (§4.3):

```
  classica   vivo  6.44..20.31:1 (mediana 20.31)   morto 4.75..6.54:1 (mediana 5.04)
             rotulos MORTOS com contraste >= o VIVO mais fraco:  1 de 26   (era 0 de 23)
  foco       vivo  5.71..13.41:1 (mediana 11.02)   morto 4.00..7.14:1 (mediana 4.10)
             rotulos MORTOS com contraste >= o VIVO mais fraco:  1 de 26   (era 22 de 22)
  fita       idem classica
```

**22 de 22 → 1 de 26 na pele Foco.** O 1 que resta é um rótulo morto sobre superfície elevada
contra um rótulo vivo sobre face de ênfase; fica **declarado**, com o número.

**E na clássica o número subiu de 0 para 1, e eu não o atribuo ao conserto.** O instrumento é meu e
não o do crítico: ele varre 26 rótulos mortos e 70 vivos onde o dele varria 23 e 54, e o rótulo
vivo mais fraco que ele mede é **6,44:1** contra os 8,79:1 do dele. Comparar 0 de 23 com 1 de 26 é
comparar duas réguas. **O número que não depende de régua é a distância entre os tokens** — 2,82:1
→ 3,66:1 e 1,88:1 → 3,27:1 —, e é ele que o portão de contraste cobra.

E o olho confirma: em `z_foco_desabilitado.png` (recorte a 3× da Galeria escura),
`Cancelar a varredura` lê-se cinzento ao lado de `Varrer o livro`, `Buscar por nome` e
`Buscar pela posição`. Era esse par que, ampliado a 2×, o crítico do ciclo 9 não conseguia
separar.

### 4.3 O que a régua achou e o olho não teria achado

Medindo pela **paleta**, dois botões por pele apareciam com a tinta viva: `Só duplicatas` e
`Imagem ausente`. São `QCheckBox` desabilitados — a folha tinha regra de `:disabled` para o
`::indicator` e **nenhuma para o rótulo**, e a linha `QWidget { color: ... }` do topo vale em todos
os estados e anula o acinzentamento que o Qt faria pela paleta. É a mesma causa que a S-506 mediu
no `QPushButton` comum, um widget adiante. Consertado:
`QCheckBox:disabled, QRadioButton:disabled { color: <morto>; }`.

### 4.4 O portão

`caissa.ui.audit.contraste` ganhou a espécie `estado`, com piso 3,0:1 e a tupla `PARES_DE_ESTADO`
para a segunda distância que aparecer. O par de legibilidade do morto continua medido — como
`grafico`, que é o piso que o produto assume para ele, com a isenção escrita.

```
  claro     300 pares   220 sob portão    0 reprovados  PASSOU   (menor folga 3,27:1)
  escuro    300 pares   220 sob portão    0 reprovados  PASSOU   (menor folga 3,03:1)
```

Eram **296 / 218 / 0**. Os quatro pares novos são os dois de cada pele.

---

## Item 5 — órfãs. **FECHADO**; a linha curta fica aberta

`ui/strings.sem_orfa(frase)` ata a **última** palavra à anterior com espaço inquebrável. Só a
última: atar mais empurra a quebra para trás e afrouxa a linha anterior — troca uma falta por
outra. Aplicado às quatro frases de estado vazio, à dica da legenda e à `MENSAGEM_VAZIA`.

`c10_orfas.py` mede o leiaute (`QTextLayout` na largura que o rótulo tem na tela), 3 peles × 3
larguras × 2 estados (com e sem livro aberto), **com estado de sessão próprio** (ver a nota no fim).
**A mesma régua nos dois lados** — `--sem-conserto` desfaz o espaço inquebrável no texto medido, e
nada mais:

```
  ANTES   18 paragrafos com quebra   ORFAS=6   ('parou.', 3,8-3,9 % da medida)   CURTAS(<20%)=0
  DEPOIS  18 paragrafos com quebra   ORFAS=0                                     CURTAS(<20%)=6
```

**6 de 18 → 0 de 18.** A pior é `'parou.'` — uma palavra, **3,8 % de uma medida de 791 px**, e ela
é a última linha da `GALERIA_VAZIA_FRASE`.

**A `'inteira.'` que o crítico nomeou também fechou**, e ela só aparece na medição com o divisor
noutra posição: numa passada anterior, com o estado de sessão da máquina, o instrumento mediu 24
parágrafos e achou `'inteira.'` a **5,7–5,8 %** — a última linha da `MENSAGEM_VAZIA`, a primeira
frase que o produto mostra. Depois do conserto ela é `'página<NBSP>inteira.'`, duas palavras.
**É o próprio motivo de o estado ter passado a ser próprio:** `sash_fraction` decide a largura do
painel, e com ela quais parágrafos quebram em quantas linhas.

**As curtas subiram de 0 para 6, e é honesto dizer por quê:** as seis órfãs viraram linhas de duas
palavras que continuam abaixo de 20 % da medida. O alvo do §6 item 10 é *"nenhuma última linha com
uma palavra só"*, e ele fechou; a linha curta é outra conta e fica **ABERTA** com o número.
`test_strings.SemOrfaTests` cobra as duas metades, inclusive que o texto visível não mudou
(`frase.split()` idêntico com e sem o espaço inquebrável).

---

## Item 6 — o 4K, rodado. **MEDIDO**; o desenho a 4K fica aberto

`capture.TAMANHOS` ganhou **3840×2160** e `capture.PELES` foi a três: **72 capturas**
(3 peles × 4 tamanhos × 6 abas), todas em `benchmarks/reports/ui/c10/`, todas com
`fonte: ... resolvida='Segoe UI' confere=sim` e **nenhuma recusa de tamanho**.

Maior retângulo vazio por painel (`c5_vazios.py` do crítico do ciclo 5, sem alteração):

| painel | 1920 claro | **3840 claro** |
|---|---|---|
| Revisão | 394,0 kpx | **3 104,2 kpx** |
| Texto | 425,0 | **2 050,6** |
| Dataset | 370,3 | **1 912,4** † |
| Estudo | 281,5 | **1 569,6** |
| Galeria | 224,0 | **1 550,0** |
| Resultado | 118,7 | **43,3** |

† **O segundo agente mede 1 905,3 kpx aqui, e não 1 912,4**, com a mesma régua (`c5_vazios.py`, sem
alteração) sobre as mesmas capturas: painel 2143×2071, maior vazio 2136×892 em (14,1135). As outras
cinco linhas da coluna de 3840 batem à decimal entre os dois. Os dois números ficam à vista; a
conclusão do item não depende de qual vale. Ver o §Reprodução independente.

**O número do crítico reproduz à decimal** (Estudo 281,5 → 1 569,6), e a medição inteira acrescenta
o que ele não tinha: **o pior painel a 4K não é a Estudo, é a Revisão, com 3 104,2 kpx** — 7,9× o
vazio dela a 1920. E o Resultado **melhora nas três peles**: ocupação do canvas 73,1 % (1920) →
**89,4 %** (3840) na clássica, 69,7 % → **87,8 %** na Foco e 77,4 % → **88,0 %** na fita; maior
vazio 118,7 → 43,3 kpx.

A 1920, os números do ciclo 8 e do ciclo 9 saem **idênticos à decimal** das minhas capturas novas
(425,0 / 394,0 / 370,3 / 281,5 / 224,0 / 118,7 claro; 408,2 / 360,5 / 353,5 / 268,0 / 208,0 / 135,6
escuro), e o item 7 também: **73,1 % claro / 69,7 % escuro, vão de 16 px, 114,5 kpx a 0,00 % de
tinta à direita da paleta**. A pele `fita` a 1920 ocupa **77,4 %** do canvas — melhor que as duas —
e tem **1 painel abaixo de 200 kpx** (Galeria, 199,4).

**O desenho a 4K fica ABERTO**, com o número, e é o item 3 do §6 da crítica.

---

## Item 7 — o censo de ícones vê as duas famílias, nas três peles. **FECHADO**

Três cegueiras da régua do ciclo 8 fecham em `c10_icones_da_janela.py`:

1. **Escopo** — `os.environ["CVOFF_SKIN"] = "classica"` cravado vira um `for` sobre `ui/pele.PELES`.
2. **Família** — `if tem_icone and not texto` vira `if tem_icone`, e as duas famílias são publicadas
   separadas. Os três botões com ícone **e** texto que o ciclo 8 criou passam a ser medidos.
3. **O lado do cromo era um literal, e ele não é constante** — `LADO_DO_CROMO = 16` valia para duas
   peles. Na `fita`, que é **compacta** (S-232), `folga + linha` dá **11 px**, e o literal
   declararia os 25 botões do cromo dela "fora da grade". Os lados são lidos do produto
   (`ui/espaco`, `medidas_da_fita.LADO_DO_ICONE`, `qt/fila.LADO_DO_ICONE`,
   `paleta_de_pecas.LADO_DO_ICONE`).

```
  === pele classica ===   GLIFOS DE TEXTO: 0
    so-de-icone   lado 16 [cromo do painel]: 18 botoes  caixas [(16,16)]  amplitude 0x0
                  tinta 17.6 % a 41.4 %  -> amplitude relativa 80.8 %
    com texto     lado 16 [cromo do painel]:  3 botoes  caixas [(16,16)]  amplitude 0x0
                  tinta 17.6 % a 36.7 %  -> amplitude relativa 70.5 %
  === pele foco ===       GLIFOS DE TEXTO: 0
    com texto     lado 18 [pilula da fila]:   4 botoes  caixas [(18,15),(18,18)]  amplitude 0x3
                  tinta 10.8 % a 46.9 %  -> amplitude relativa 125.1 %
  === pele fita ===       GLIFOS DE TEXTO: 0
    so-de-icone   lado 11 [cromo do painel]: 19 botoes  caixas [(11,11)]  amplitude 0x0
    so-de-icone   lado 20 [fita, compacto]:   6 botoes  caixas [(20,20)]  amplitude 0x0
    com texto     lado 20 [fita, compacto]:  18 botoes  caixas [(20,9)..(20,20)]  amplitude 0x11
                  tinta 11.2 % a 48.5 %  -> amplitude relativa 124.7 %
  GLIFOS DE TEXTO em TODAS as peles: 0
```

**São 12 grades medidas (3 peles × as famílias de cada uma), e a caixa é única em 10.** As duas que
não são estão aqui com o número: a fila da Foco (amplitude **0×3 px**) e a fita compacta
(**0×11 px**). A causa é a mesma nas duas:
`ui/icones.na_grade` enche o **lado maior**, e um desenho largo-e-baixo (`Desfazer`, `Refazer`,
`Limpar`) sai com altura menor que o lado pedido. Na grade de 16 px isso não aparecia porque
aqueles três desenhos não estavam nela. **ABERTO, com número.** A tinta continua aberta como no
ciclo 8, agora medida em quatro grades em vez de uma.

O `c7_icones_da_janela.py` do crítico, rodado sem alteração (ele conhece duas peles):
**`GLIFOS DE TEXTO fazendo papel de icone: 0`** nas duas.

---

## Item 8 — `nomear_o_que_o_cromo_nao_desenha` pergunta pela visibilidade. **FECHADO**

O crítico montou seis cromos de mentira e o método respondeu certo em cinco; o caso 5 —
*"um botão escondido com o nome"* — fazia a barra **não** escrever o nome, porque o `text()` de um
botão escondido continua lá.

**É `isVisibleTo(cromo)` e não `isVisible()`, e a diferença foi medida.** O método é chamado de
`_montar_o_cromo`, que corre no `__init__` da janela — **antes** do `show()`. Com `isVisible()`
todos os botões do cromo respondem `False` ali, o conjunto sai vazio, e a barra do visor escreve o
nome que a fita já escreve: dois controles com o mesmo rótulo, que é o item que este método fecha.
`isVisibleTo` pergunta o que importa: *este botão aparece quando o cromo aparecer?*

`c10_vazio_na_tela.py`, **3 peles × 4 larguras (incluindo o piso de 1066) × 3 nomes citados**:

```
  classica: LINHAS=12 NAO_DESENHADOS=0 DUPLICADOS=0
  foco:     LINHAS=12 NAO_DESENHADOS=0 DUPLICADOS=0
  fita:     LINHAS=12 NAO_DESENHADOS=0 DUPLICADOS=0
  ESTADO VAZIO em TODAS as peles: 0 nao desenhados, 0 duplicados
```

**Nunca dois, nunca zero** — e a metade difícil é a primeira. `c8_vazio_na_tela.py`, sem alteração:
**30 de 30 `DESENHADO=sim`, 0 `NAO`**.

---

## Item 9 — a janela abre sem torch. **FECHADO**, e ele cobrou um preço que está no §9.4

*Este item é inteiro do segundo agente do ciclo (ver a Nota de autoria, no topo). Ele não veio da
crítica do ciclo 9: veio de `packaging/pendencias/0001-torch-fora-do-escopo-de-modulo.patch`, que
o agente de empacotamento deixou endereçado a esta frente.*

### 9.1 O que estava errado

O instalador leve não leva torch dentro (o torch é instalado na primeira execução, com a roda
certa para a placa da máquina). Entre instalar e rodar o assistente existe uma janela de tempo em
que `Caissa.exe` é chamado sem torch, e nela **o programa não abre**. Não abre degradado: não
abre, com `ModuleNotFoundError: No module named 'torch'` escapando do auto-teste.

**E o diagnóstico do ciclo 1 do F12 estava errado sobre onde consertar.** Ele dizia que
`qt/janela.py` importa torch no topo. Ela não importa: `grep -n torch qt/janela.py` devolve **duas
linhas, as duas comentário**. Ela importa quatro módulos que, transitivamente, chegam lá.

### 9.2 O conserto: cortar as arestas, e não adiar o torch nas folhas

Quatro arquivos, **nenhum deles em `qt/`** — e é por isso que o patch declara o dono como F9 e não
como "o dono de `qt/`":

* `checkpoint.py` — `import torch` desce para `_load_raw` e `save_checkpoint` (0 usos no escopo de
  módulo).
* `inference.py` — `torch`, `torch.nn` e `from .model import ...` saem do topo; `nn.Module` e
  `ArchConfig` viram `TYPE_CHECKING` (a linha 1 já é `from __future__ import annotations`, então
  toda anotação é texto).
* `service.py` — `from .dataset import append_training_sample` desce para o único método que o usa.
* `ui/pedido_de_treino.py` — `from ..training import TrainingRun` vai para `TYPE_CHECKING`.

`dataset`, `training`, `model` e `augment` **continuam exigindo torch, e devem**: os quatro
definem `nn.Module`/`Dataset` no escopo de módulo. O que muda é que abrir a janela deixa de
importá-los.

### 9.3 A régua, e ela tem a prova de vida embutida

`benchmarks/reports/ui/c10/c10_sem_torch.py` bloqueia `torch`, `torchvision`, `torchgen` e
`functorch` num `MetaPathFinder` no topo de `sys.meta_path`, num processo limpo, e importa a
árvore. **Nada no ambiente de ninguém muda** — não há `pip uninstall` no caminho.

```
  === com torch BLOQUEADO, o que a janela precisa ===
  ok      chess_diagram_ocr.qt.janela
  ok      chess_diagram_ocr.service
  ok      chess_diagram_ocr.qt.campo
  ok      chess_diagram_ocr.checkpoint
  ok      chess_diagram_ocr.inference
  ok      chess_diagram_ocr.ui.pedido_de_treino
  ok      chess_diagram_ocr.field_eval

  === com torch BLOQUEADO, o que DEVE continuar exigindo (treino e rede) ===
  FALHOU  chess_diagram_ocr.dataset    <- dataset.py:12   import torch
  FALHOU  chess_diagram_ocr.training   <- training.py:31  import torch
  FALHOU  chess_diagram_ocr.model      <- model.py:23     import torch
  FALHOU  chess_diagram_ocr.augment    <- augment.py:38   import torch

  modulos da JANELA que falham sem torch: 0 de 7
  modulos da REDE que passaram sem torch (deveria ser 0): 0 de 4
  Veredito: PASSOU
```

**A segunda metade é a prova de vida, e ela é a razão de a primeira valer alguma coisa.** Um
`MetaPathFinder` que não bloqueasse nada devolveria `ok` nas onze linhas. As quatro `FALHOU` provam
que o bloqueio morde; as sete `ok` provam que a janela passou por baixo dele.

### 9.4 O que este conserto quebrou, e como cada metade foi respondida

**Duas reprovações novas na suíte do tronco**, as duas achadas pela primeira execução depois do
patch. Nenhuma foi afrouxada, e as três contagens medidas são estas:

```
  antes do patch   3 failed, 4486 passed, 2 skipped   (as tres de sempre)
  depois do patch  5 failed, 4484 passed, 2 skipped   <- test_checkpoint e test_field_eval
  depois de (a)    4 failed, 4485 passed, 2 skipped   <- so test_field_eval, que fica ABERTO
```

**(a) `test_checkpoint.py::AtomicWriteTests::test_uma_escrita_interrompida_preserva_o_checkpoint_anterior` — CONSERTADO no produto.**
A guarda da S-57 alcança o `torch.save` por
`patch("chess_diagram_ocr.checkpoint.torch.save", side_effect=OSError("disco cheio"))`. Tirar
`import torch` do topo tira o **nome** `checkpoint.torch`, e o remendo deixa de encontrar onde
pegar. `checkpoint.py` ganhou um `__getattr__` de módulo (PEP 562) que resolve `torch` **na hora
do acesso**: o nome existe, importar o módulo não dispara nada, e quem acessa recebe o mesmo
objeto de `sys.modules["torch"]` que o `import torch` de dentro das duas funções receberá — por
isso o remendo é visto lá dentro. `tests/test_checkpoint.py`: **27 passed**, sem uma linha de teste
alterada; e `c10_sem_torch.py` continua **PASSOU** depois da mudança.

**(b) `test_field_eval.py::ImpressaoDaMedicaoTests::test_todo_relatorio_corrente_mediu_o_codigo_de_hoje` — ABERTO, e a decisão de não mexer é deliberada.**
A guarda da S-425 tem digest do **fecho de imports** do caminho de medição, sobre a árvore
sintática com docstring e comentário removidos. Medido:

```
  modulos no fecho HOJE: 30       (antes: 30 -- nenhum entrou, nenhum saiu)
  field_20260822_s99.json : digest mudou em ['checkpoint', 'inference', 'service']
  controle_20260822.json  : digest mudou em ['checkpoint', 'inference', 'service']
  mhsp_20260822.json      : digest mudou em ['checkpoint', 'inference', 'service']
  s108_20260822.json      : digest mudou em ['checkpoint', 'inference', 'service']
```

**O conjunto de módulos não mudou; três digests mudaram, e mover um `import` é mudança de código
de verdade** — `ast.dump` traz o `Import` como traz qualquer nó, e é assim que a guarda foi
desenhada de propósito (ela já foi consertada uma vez para **parar** de reagir a docstring, e não
a código). Semanticamente o meu conserto é só instante de import, mas **um digest não sabe disso, e
a guarda diz no docstring que não é papel dela saber**.

O próprio teste nomeia as duas saídas honestas: remedir com `cvoff-field --json`, ou tirar o
relatório de `RELATORIOS_CORRENTES` declarando-o histórico. **Eu não fiz nem uma nem outra**, e
digo por quê sem atenuar: as duas reescrevem `docs/metrics/*.json`, que é dado de medição de
campo — quatro relatórios que documentos citam como correntes, sobre 68 páginas e quatro modelos.
Remedir republicaria números de outra frente com a minha assinatura; e a impressão nova gravaria
`dirty: true`, porque hoje a árvore do tronco tem meia dúzia de agentes mexendo nela, contra o
`dirty: false` num commit limpo que o arquivo publicado carrega. **Seria trocar uma proveniência
boa por uma pior.**

**Mas eu não deixo a afirmação "as métricas não mudam" sem número.** Remedi o relatório da S-99
para um **arquivo temporário** (`--json <temp>`, que é a única coisa que o `cvoff-field` escreve
além do log) e comparei métrica a métrica com o publicado:

```
  metricas comparadas (excluindo os campos de tempo): 1080
  metricas diferentes                               :    0

    export_rate          publicado=0.8696   remedido=0.8696
    exact                publicado=93       remedido=93
    detection_recall     publicado=0.9478   remedido=0.9478
    detection_precision  publicado=0.9732   remedido=0.9732
    exported/detected/legal/above_gate     100 / 112 / 108 / 100  nos dois
    pages/annotated/false_positives         68 / 115 / 3          nos dois
    clean_export_rate    publicado=0.8515   remedido=0.8515
    conditional_exact    publicado=0.9688   remedido=0.9688

  modulos com digest diferente: 3 -> ['checkpoint', 'inference', 'service']
```

As **únicas** 64 diferenças em 1 150 campos são `seconds` e `seconds_per_diagram` — por livro e no
total —, que mudam entre quaisquer duas execuções e não são medida de qualidade.

**Fica ABERTO, com o nome dos três módulos, dos quatro relatórios e agora com a conta de que a
remedição não move nada**, para quem é dono de `docs/metrics/`: são quatro invocações de
`cvoff-field --json`, ~1 min por modelo, de preferência numa árvore limpa para o `dirty` sair certo.

**As três reprovações de base do tronco continuam sendo as três de sempre** (§Suítes), e nenhuma
delas é minha.

---

## Os portões, todos rodados

| portão | resultado |
|---|---|
| **Teclado + nome + papel, TODAS as peles** | **216 / 240 / 360 focáveis; 0 sem nome, 0 sem papel, 0 nome vazio, 0 fora do Tab. PASSOU nas três** |
| **Ícones, TODAS as peles** | **0 glifos nas três.** Caixa única em **10 de 12** grades; amplitude 0×3 (fila) e 0×11 (fita) abertas |
| Contraste WCAG AA | **300 pares / 220 sob portão / 0 reprovados** nas duas peles; menor folga 3,27:1 e 3,03:1. **PASSOU** |
| **Execução (operação de fundo)** | tronco real: 5 aberturas em 9 ações, **0 sem cobertura, 0 não atribuídas. PASSOU**. Sabotagens: **8/8 + 8/8**, 9 controles negativos calados. Régua gêmea no tronco: `tests/test_busy.PortaoDeExecucaoTests`, 7 testes -- e foi ela que achou o §2.7 |
| Progresso | **8 indicadores, 13 operações de fundo, 0 invisíveis, 0 defeitos bloqueantes**; faixa medida **por operação**, com a faixa de repouso ao lado |
| Estado vazio na tela | **36 linhas, 0 não desenhados, 0 duplicados** (3 peles × 4 larguras) |
| Órfãs | **0 de 18** parágrafos com última linha de uma palavra (eram 6) |
| Estado morto | **3,66:1 / 3,27:1 / 3,66:1**, acima do piso de 3,0. Mortos ≥ vivo mais fraco: 1 de 26 nas três |
| Vazio de painel | 10 de 12 acima de 200 kpx a 1920; **a 3840 os seis ficam acima, o pior com 3 104,2 kpx** |
| Ocupação | **73,1 %** clara / **69,7 %** escura / **77,4 %** fita; vão 16 px; 114,5 kpx à direita da paleta |
| Rodapé (elisão) | `c7_rodape_elisao.py` sem alteração: **0 ELIDE** nas três larguras |
| Rótulos repetidos | `c7_rotulos_repetidos.py` sem alteração: **2 pares divergentes**, os dois na pele Foco |
| Janela pequena | `c7_janela_pequena.py` sem alteração: `minimumSize` **1066×735**, **0 controles fora** |
| Nada bloqueia > 16 ms | **REPROVOU nas três execuções, 7 operações.** Medianas de 3: abrir PDF **272 ms**, p.121 **110**, p.41 **108**, p.42 **108**, aba Dataset **90**, rasterizar **77**, aba Galeria **30** |
| fps ≥ 55 @ p95 | **PASSOU nas três execuções**, com a máquina em repouso: juntos 89,7 · 85,6 · 84,5 → mediana **85,6**; pan 524,6–585,1; zoom 62,8 · 65,8 · 64,0 → mediana **64,0** (16 % de folga). Com as duas suítes rodando ao lado, o zoom deu 60,6 · 54,2 · 50,0 e **reprovou duas vezes** — os dois números estão aqui porque o segundo é sobre a máquina e não sobre o produto |
| Capturas | **72** (3 peles × 4 tamanhos × 6 abas), fonte do produto conferida nas três, 0 recusas de tamanho |
| **A janela abre sem torch** | `c10_sem_torch.py`: **7 de 7** módulos da janela importam com `torch`/`torchvision`/`torchgen`/`functorch` bloqueados; os **4 de 4** da rede continuam exigindo (é a prova de vida do próprio bloqueio). **PASSOU** |

---

## O que continua aberto, com o número

| item | número | onde |
|---|---|---|
| bloqueio > 16 ms | REPROVA, 7 operações; a pior é `abrir PDF` com **272 ms** (mediana de 3) | medido hoje |
| E/S na thread da janela | inalterado desde o ciclo 8: `_abrir_cache_de_posicoes` (SQLite) dentro de `abrir PDF` | declarado |
| vazio de painel a 1920 | **10 de 12** acima de 200 kpx | medido hoje |
| **vazio de painel a 4K** | **6 de 6**; o pior é a **Revisão com 3 104,2 kpx**, e não a Estudo | medido hoje |
| poço à direita da paleta | **114,5 kpx** a 0,00 % de tinta a 1920 claro | medido hoje |
| tinta dos ícones | 17,6 %–41,4 % (cromo 16 px) e **11,2 %–48,5 %** (fita 20 px) | medido hoje |
| **caixa do ícone fora da grade de 16** | 2 de 12 grades: amplitude **0×3 px** (fila, 18 px) e **0×11 px** (fita, 20 px) | medido hoje |
| última linha curta | **6 de 18** parágrafos com última linha abaixo de 20 % da medida | medido hoje |
| rótulo morto mais legível que o vivo mais fraco | **1 de 26** em cada pele (era 22 de 22 na Foco) | medido hoje |
| falso positivo da contagem | `nome = self.nome_do_livro()` acusa; 3 de 4 controles negativos calados | medido hoje |
| um rótulo, um controle | **2** pares com estados divergentes, os dois na pele Foco | medido hoje |
| zoom da fita só-de-ícone | 6 de 24 botões da fita ficaram sem rótulo; nos 2 de zoom o olho sente | visto hoje |
| janela pequena | `minimumSize` **1066×735**: num monitor de 1024×768 a janela transborda 42 px | medido hoje |
| barra determinada no dataset | precisa de callback em `dataset_browser.load_rows`, fora do que esta frente escreve | declarado |
| **impressão de código dos 4 relatórios de campo** | `test_field_eval::test_todo_relatorio_corrente_mediu_o_codigo_de_hoje` REPROVA: **3 módulos** (`checkpoint`, `inference`, `service`) mudaram de digest em **4 relatórios**; o fecho continua com **30** módulos, nenhum entrou nem saiu. Remedido em arquivo temporário: **1 080 métricas comparadas, 0 diferentes** | medido hoje; §9.4b |

---

## O que só o olho achou

**A.** **Seis dos 24 botões da fita ficaram só-de-ícone**, e os outros 18 continuam com rótulo — o
glifo (`-`, `+`, `◀`, `▶`, `|◀`, `▶|`) era o que os fazia *parecer* rotulados. Nos quatro de
navegação isso é o certo (eles nunca tiveram palavra); nos dois de zoom o olho sente a falta, numa
fila em que o vizinho da esquerda diz `Ajustar à página`. Visível em `z_fita_ribbon_esq.png`. Está
no §1.6, declarado e não corrigido, com o motivo.

**B.** A 3840×2160 o painel da **Revisão** é o pior vazio da janela, e não o da Estudo que o crítico
mediu — 3 104,2 kpx contra 1 569,6. Olhando `prancha_claro.png` a coluna de 3840 é uma folha em
branco com uma tabela de cabeçalho no topo em quatro das seis abas.

**C.** Medindo pela paleta e não pelo pixel, dois `QCheckBox` desabilitados por pele desenhavam com
a tinta **viva**. Está no §4.3, consertado.

---

## O que mudou, arquivo a arquivo

**Nossa suíte**

* `src/caissa/ui/audit/execucao.py` — **novo**: o portão de execução (`Vigia`, `observar`,
  `auditar`, `auditar_a_sabotagem`).
* `src/caissa/ui/audit/teclado.py` — `peles_registradas`, `auditar_as_peles` (um subprocesso por
  pele), `--pele`/`--json`, `Controle.grupo` + `nome_qualificado()`, `_grupo_de`, `_descartar`, o
  motivo `quebra de linha no nome`, e a tabela com uma linha por pele.
* `src/caissa/ui/audit/capture.py` — `PELES` a três, `TAMANHOS` com 3840×2160, `capturar_uma_pele`
  e um subprocesso por pele.
* `src/caissa/ui/audit/contraste.py` — espécie `estado`, `PARES_DE_ESTADO`, `pares_de_estado`.
* `src/caissa/ui/audit/progresso.py` — `TOTAL_DE_REFERENCIA`, `ASSENTAR_MS`, `faixa_por_operacao`,
  `determinado_medido`, a faixa de repouso na evidência, e `PROFUNDIDADE_DA_CADEIA` na heurística
  de contagem.
* `tests/unit/ui/test_execucao.py` — **novo**, 12 testes.
* `tests/unit/ui/test_medicao.py` — `TestTodasAsPeles`, `TestNomeQualificado` e
  `TestQuebraDeLinhaNoNome`: **13 testes novos**; e a sabotagem da faixa passa a ter uma terceira
  metade (a barra que devolve a mesma faixa com e sem ocupação).
* `tests/unit/ui/test_arquitetura.py` — `capture` e `execucao` entram no teste de importação sem Qt.
* `benchmarks/reports/ui/c10/` — as 72 capturas, as três pranchas de contato, os instrumentos
  (`c10_icones_da_janela.py`, `c10_vazio_na_tela.py`, `c10_orfas.py`, `c10_estado_morto.py`,
  `c10_repetidos.py`, `c10_prancha.py`, `c10_zoom.py`), as duas provas de vida
  (`c10_prova_de_vida.py`, `c10_faixa_tardia.py`) e as três árvores de sabotagem (`sab_c9/`, cópia
  fiel do crítico; `sab_c9x/`, a transcrição executável; `sab_c10/`, as oito minhas).
* `benchmarks/reports/ui/c10/c10_sem_torch.py` — **novo (item 9)**: a régua do bloqueio de torch,
  com a prova de vida embutida (os 4 módulos da rede que **têm** de falhar).

**Tronco** (`chess_diagram_ocr/`)

* `ui/comandos.py` — `Comando.so_glifo`, `so_glifo(acao)`, `acoes_so_de_glifo()`.
* `ui/strings.py` — `ESPACO_INQUEBRAVEL`, `sem_orfa`, e as cinco frases atadas.
* `ui/tokens.py` — `TEXTO_MORTO` nas duas paletas, em `PAPEIS` e em `CROMO`.
* `ui/folha_de_estilo.py` — todo `:disabled` de letra passa a `TEXTO_MORTO`; regra nova para
  `QCheckBox:disabled, QRadioButton:disabled`; `PAPEIS_DA_PALETA_MORTA` atualizado.
* `qt/fita.py` — `vestir` no lugar do `setIcon` cru, `setAccessibleName`, `_so_de_icone`, o nome do
  grupo no contêiner, e a guarda do seguidor de estado.
* `qt/fila.py` — `REGIAO`, `setAccessibleName` na pílula e na fila, `vestir`.
* `qt/painel_do_pdf.py` — `isVisibleTo(cromo)` em `nomear_o_que_o_cromo_nao_desenha`.
* `qt/painel_de_resultado.py` — `MENSAGEM_VAZIA` passa por `strings.sem_orfa`.
* `checkpoint.py` — **(item 9)** `import torch` desce para `_load_raw` e `save_checkpoint`; e um
  `__getattr__` de módulo (PEP 562) mantém o nome `checkpoint.torch` resolvendo preguiçosamente,
  que é o que a guarda da S-57 remenda. Nenhuma linha de teste foi tocada.
* `inference.py` — **(item 9)** `torch`, `torch.nn` e `from .model import ...` saem do escopo de
  módulo; `nn.Module` e `ArchConfig` passam a `TYPE_CHECKING`; os nomes de `.model` entram por
  import local no topo das três funções que os avaliam.
* `service.py` — **(item 9)** `from .dataset import append_training_sample` desce para
  `save_sample`, que é o único método que o usa.
* `ui/pedido_de_treino.py` — **(item 9)** `from ..training import TrainingRun` vai para
  `TYPE_CHECKING` (só serve à assinatura de `summarize_run`).
* `tests/test_qt_fita.py` — 5 testes novos (o glifo que não se desenha, o nome por extenso nos dois
  modos, a quebra de linha, o nome do grupo, o seguidor que não repõe o glifo).
* `tests/test_qt_fila.py` — **novo**, 4 testes.
* `tests/test_ui_tokens.py` — `PARES_DE_ESTADO` e 3 testes do estado morto.
* `tests/test_strings.py` — `SemOrfaTests`, 6 testes.
* `tests/test_busy.py` — `PortaoDeExecucaoTests` e o `_Vigia`, a régua gêmea do portão de
  execução: **7 testes** (o sétimo é o `QThread` restaurado; ver §2.7). A suíte do tronco vai de
  4 479 para **4 486** passados por causa deles.

---

## Suítes

*Esta seção é a do segundo agente: as quatro execuções abaixo são dele, rodadas depois de o item 9
entrar. As do primeiro agente estão citadas no fim, porque explicam por que a linha "sem o
`test_packaging.py`" existe.*

| suíte | execução 1 | execução 2 | igual? |
|---|---|---|---|
| **Tronco** (`-p no:randomly`) | **4 failed, 4 485 passed, 2 skipped, 4 536 subtests** em 288,00 s | **4 failed, 4 485 passed, 2 skipped, 4 536 subtests** em 301,31 s | **sim, e as mesmas quatro reprovações** |
| **Nossa** (`.venv`, `pytest tests -q`) | **3 137 passed, 2 skipped, 0 failed** em 826,50 s | **3 141 passed, 1 skipped, 0 failed** em 804,76 s | verde nas duas; **a contagem não bate — ver abaixo** |
| **Nossa, sem `tests/integration/test_packaging.py`** | **3 049 passed, 1 skipped, 0 failed** em 780,14 s | **3 049 passed, 1 skipped, 0 failed** em 780,03 s | **sim — idênticas, e até o mesmo pulo** |
| `tests/unit/ui` sozinha | **161 passed, 0 failed** em 3,12 s | idem | sim |

### O tronco fecha duas vezes igual, e as quatro reprovações são três de sempre mais uma minha

```
  test_docs::test_a_arvore_do_README_lista_todo_modulo_do_pacote
      desenho_de_diagrama.py, pdf_substituicao.py
  test_editor_model::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter
      biblioteca.py, cortina.py, selecao_de_area.py, substituicao.py
  test_strings::test_no_ui_string_uses_an_unaccented_portuguese_word
      biblioteca.py: 'cabecas'   substituicao.py: 'pagina' (x4)   tokens.py: 'SELECAO'
  test_field_eval::test_todo_relatorio_corrente_mediu_o_codigo_de_hoje      <<< do item 9
      checkpoint, inference, service mudaram de digest -- ver §9.4b
```

`diff` das duas listas de `FAILED`: **idênticas**. As três primeiras são as que o crítico do ciclo
9 enumerou e nenhuma nomeia arquivo que esta frente toque; a quarta é minha, está no §9.4b com o
número, e é a única do documento que fica aberta por decisão e não por falta de tempo.

### A nossa suíte fecha VERDE nas duas, e a contagem que não bate tem dono

**Zero reprovações nas duas execuções** — e isso é uma mudança em relação ao primeiro agente, que
mediu 2 e 3. O motivo é bom: as reprovações dele eram `tests/integration/test_packaging.py` lendo
`packaging/caissa.spec` e `installer.iss` **enquanto o agente de empacotamento os reescrevia**.
Esse trabalho aterrissou; rodado sozinho agora, `test_packaging.py` devolve **96 passed, 0 skipped**
(eram 53 passed + 2 skipped às 18:10 desta mesma sessão).

**E é o mesmo agente que explica os 4 testes de diferença entre as minhas duas execuções.** O
`test_packaging.py` parametriza sobre **o conteúdo do bundle em `dist/`**, e o número de casos
coletados muda quando o bundle muda:

```
  nossa r1 terminou 18:50   3137 passed, 2 skipped   (pulou a medicao do custo do torch congelado)
  dist/Caissa            reescrito 19:02   } pelo agente de empacotamento,
  dist/caissa-...-.7z    escrito   19:03   } ENTRE as minhas duas execucoes
  nossa r2 terminou 19:03   3141 passed, 1 skipped   (a mesma medicao ja tinha bundle e rodou)
```

O pulo que desaparece é literalmente esse: `test_packaging.py:601`,
*"a medicao do custo do torch congelado vem do ciclo 1"*, que pula quando não há o que medir. O
único pulo que sobrevive às duas é o de sempre — `test_fonts.py:333`, WOFF2 sem o compressor
Brotli neste ambiente.

**Por isso a linha "sem o `test_packaging.py`" existe, e ela responde a pergunta de determinismo
desta frente com o número:**

```
  A:  3049 passed, 1 skipped, 0 failed  em 780,14 s
  B:  3049 passed, 1 skipped, 0 failed  em 780,03 s
      mesma contagem, mesmo pulo (test_fonts.py:333, Brotli), zero reprovações nas duas,
      e 0,11 s de diferença em treze minutos
```

**Duas execuções idênticas e verdes, que é o padrão que este projeto exige** — e ele existe porque
um defeito de subconjunto não determinístico já deixou esta suíte vermelha uma execução em três. A
variação de 4 testes entre as execuções da suíte **inteira** está, portanto, **toda** no arquivo
que lê o bundle de outro agente; o que esta frente escreve não varia.

**E este é exatamente o número que o primeiro agente estava esperando quando foi interrompido.**
Ele mediu `3049 passed, 1 skipped, 0 failed` e caiu aguardando a segunda execução confirmar. A
segunda execução confirma, e a terceira e a quarta (a suíte inteira) confirmam a cor.

**Zero reprovações em `tests/unit/ui/`** (161 de 161) em todas as execuções.

**Zero reprovações em `tests/unit/ui/`** (161 de 161), e zero em tudo o mais: a linha "sem o
`test_packaging.py`" acima é a mesma suíte com **só aquele arquivo** de fora, duas vezes.

---

## Reprodução independente (segundo agente)

Rodei os portões e os instrumentos **sem alterar uma linha do que estava em disco**, para conferir
se o produto entregue devolve os números que este documento publica. Cada linha abaixo é um comando
que eu rodei nesta sessão.

| o que rodei | o que saiu | bate com o §? |
|---|---|---|
| `caissa.ui.audit.teclado` (as três peles) | `classica 216 / foco 240 / fita 360` focáveis, **0 sem nome, 0 sem papel, 0 nome vazio, 0 fora do Tab**, `Veredito de TODAS as peles: PASSOU` | §1.5, à unidade |
| `c10_icones_da_janela.py` | `GLIFOS DE TEXTO em TODAS as peles: 0`; **12 grades**, caixa única em **10**; as duas de fora com amplitude **0×3 px** (fila 18 px) e **0×11 px** (fita 20 px) | §7, à unidade |
| `c10_prova_de_vida.py` | sem `setAccessibleName` → teclado **REPROVOU**, `fita 360 focáveis, 90 nome vazio` (15 por aba × 6); glifo de volta → censo **REPROVOU**, `6 glifos` na fita; `qt/fita.py` restaurado, sha256 `1f27fac6…4a` **confere: sim** | §1.4, à unidade |
| `caissa.ui.audit.execucao --sabotagem sab_c9x` | **8 de 8** formas pegas, **4 de 4** controles negativos calados | §2.2 |
| `caissa.ui.audit.execucao --sabotagem sab_c10` | **8 de 8** formas pegas, **5 de 5** controles negativos calados | §2.3 |
| `caissa.ui.audit.execucao --sabotagem sab_c9` | `MODULO NAO EXECUTAVEL: cannot import name 'QtConcurrent' from 'PyQt6.QtCore'` — confirmo que a cópia fiel do crítico não roda neste venv | §2.2 |
| `caissa.ui.audit.execucao` (tronco vivo) | **5 aberturas em 9 ações**, `0 sem cobertura, 0 nao atribuidas`, **PASSOU**; as três origens são `marcas.py::pedir:169`, `trabalho.py::_comecar:130`, `painel_do_dataset.py::_reler_agora:428` | §2.4, à unidade |
| `c10_faixa_tardia.py` | sem sabotagem **0/0**; tique de 40 ms **0/0**; "nunca troca de modo" **4 bloqueantes, 4 divergências**; `qt/rodape.py` restaurado, sha256 `8f45d98e…26` **confere: sim** | §3.3, à unidade |
| `caissa.ui.audit.contraste` | claro **300 pares / 220 sob portão / 0 reprovados**, menor folga **3,27:1**; escuro idem com **3,03:1**. **PASSOU** | §4.4, à unidade |
| `c10_estado_morto.py` | `classica 3,66:1` · `foco 3,27:1` · `fita 3,66:1`; mortos ≥ vivo mais fraco **1 de 26** nas três | §4.2, à unidade |
| `c10_orfas.py` | **0 órfãs de 18**, 6 curtas; com `--sem-conserto`, **6 órfãs de 18**, 0 curtas | §5, à unidade |
| `caissa.ui.audit.progresso` | **8 indicadores, 13 operações de fundo, 0 invisíveis**, `Nenhum defeito bloqueante de progresso` | §Portões |
| `c5_vazios.py` (do crítico do ciclo 5, sem alteração) nas 6 capturas 4K claras | Revisão **3 104,2** · Texto **2 050,6** · Dataset **1 905,3** · Estudo **1 569,6** · Galeria **1 550,0** · Resultado **43,3** kpx | §6 — **uma divergência, abaixo** |
| `pytest tests/unit/ui -q` | **161 passed** em 3,12 s | §Suítes |
| `c9_icones_com_texto.py` (do crítico, sem alteração) | vê os **3** botões com ícone **e** texto (`Ler esta página`, `Diagrama anterior`, `Próximo diagrama`); grupos de irmãos 45..87 px², **1,9×** | §7 e a alínea 8 da carta |
| `c9_pele_fita.py` (do crítico) | as **18** capturas da fita, nas três larguras | §1.6 |
| `c7_icones_da_janela.py` (do crítico do ciclo 7, sem alteração) | `GLIFOS DE TEXTO fazendo papel de icone: 0` nas **duas** peles que ele conhece | §Portões |
| `c10_vazio_na_tela.py` | `classica/foco/fita: LINHAS=12 NAO_DESENHADOS=0 DUPLICADOS=0` — **36 linhas**, 3 peles × 4 larguras | §8, à unidade |
| `c10_sem_torch.py` | **7 de 7** módulos da janela importam com torch bloqueado; **4 de 4** da rede continuam falhando (a prova de vida) | §9.3 |
| `cvoff-field --json <temp>` + comparação | **1 080 métricas comparadas, 0 diferentes**; só `seconds` muda | §9.4b |

**A divergência, e ela é minha contra o §6, não contra o crítico.** O §6 publica o Dataset a 4K
como **1 912,4 kpx**; a mesma régua, nas mesmas capturas, me devolve **1 905,3 kpx** (painel
2143×2071, maior vazio 2136×892 em (14,1135)). Os outros cinco batem à decimal, inclusive os dois
que o crítico tinha medido (Estudo **1 569,6** e o Resultado que **melhora**, 43,3). Não sei
reconstruir de onde saiu o 1 912,4 — publico o meu número medido e deixo os dois à vista; a
conclusão do item (**os seis painéis acima de 200 kpx a 4K, e o pior é a Revisão e não a Estudo**)
não depende de qual dos dois vale.

**O que eu deliberadamente NÃO remedi, e por quê.** Os dois portões de tempo — `bloqueio`
(*nada bloqueia > 16 ms*) e `quadros` (*fps ≥ 55 @ p95*) — ficam com os números que o primeiro
agente publicou. **A máquina não estava ociosa durante a minha passada**: além das minhas quatro
execuções de suíte, havia um processo Python de outro agente com **681 s de CPU acumulados**,
aberto desde as 09:57. Remedir fps numa máquina assim produziria um número sobre a máquina e não
sobre o produto — que é exatamente a armadilha que o primeiro agente já documentou na linha de fps
do §Portões, onde as duas medições (ociosa e disputada) estão lado a lado. Os portões que eu
reproduzi acima são todos de contagem e de pixel, e nenhum deles depende do relógio.

**Sobre caminho de saída, que a ordem de serviço mandou conferir antes de rodar.** Dois
instrumentos do crítico (`c9_pele_fita.py` e `c9_quatro_k.py`) gravam em
`Path(__file__).parent` — isto é, **dentro de `benchmarks\reports\critique\ui\c9\`**, que esta
frente não pode tocar. Rodei-os a partir de uma **cópia** num diretório temporário (SHA-256
conferido igual ao original antes de rodar), e por isso as capturas saíram lá e não sobre as do
crítico. Conferido depois: os `mtime` de `zfita_1920x1080_estudo.png`,
`z4k_claro_3840x2160_estudo.png` e `capture_estado_fita.json` continuam **13:51/13:53**, de antes
desta sessão. Os demais instrumentos do crítico (`c9_icones_com_texto.py`, `c9_estado_morto.py`,
`c9_orfas.py`, `c9_vazio_no_piso.py`, `c9_cromo_menu.py`, `c5_vazios.py`, `c5_regioes.py`) não
gravam nada — conferido por busca de `write_text`/`save`/`open(...,'w')`/`json.dump` antes de rodar.
Exportei `PYTHONDONTWRITEBYTECODE=1` em toda invocação, que é a falta que o primeiro agente
registrou no fim deste documento.

### O que os portões provam sobre a **largura** da medição

O bloqueante do ciclo 9 existiu porque um portão amostrava uma pele de três. Conferi que isso não
pode voltar a acontecer em silêncio, e não pela leitura do código:

```
  ui/pele.PELES         -> ['classica', 'fita', 'foco']
  capture.PELES         -> ['classica', 'fita', 'foco']
  iguais (teste verde)  -> True
  sem a fita, iguais    -> False   <- o teste REPROVA
  e o 4K esta em TAMANHOS -> True
```

`teclado.peles_registradas()` lê `ui/pele.PELES` do produto, e
`test_medicao.TestTodasAsPeles.test_a_captura_cobre_toda_pele_registrada` compara **conjunto com
conjunto** — ele cai tanto se uma pele nova entrar no menu sem entrar na captura quanto no
contrário. A linha `sem a fita, iguais -> False` é a prova de vida dele.

### O que eu vi, olhando

Olhei as **72 capturas** pelas três pranchas de contato (`prancha_claro.png`, `prancha_escuro.png`,
`prancha_fita.png` — 24 cada, 6 abas × 4 larguras), e depois os recortes a 3×. O que confirmo com o
olho:

* **O glifo saiu, e o desenho ficou.** Em `z_fita_ribbon_dir.png` os quatro botões de navegação
  desenham um traço só — `<`, `>`, `|<`, `>|` como desenho, sem o `◀` de 5×3 px ao lado; e
  `Desfazer`, `Refazer`, `Limpar` mostram ícone **e** rótulo, que é a família que o censo do ciclo
  8 não enxergava.
* **E o item aberto do §1.6 é visível, não é retórica.** Em `z_fita_ribbon_esq.png` os dois botões
  de zoom (a lupa com `-` e com `+`) ficam **sem palavra nenhuma** encostados em
  `Ajustar à largura` e `Ajustar à página`, que têm as suas. Numa fita cuja regra é "ícone grande
  **com** rótulo", esses dois são a exceção que se vê de longe.
* **O estado morto separa-se do vivo na pele Foco.** Em `z_foco_desabilitado.png`,
  `Cancelar a varredura` lê-se claramente mais apagado que `Varrer o livro`, `Buscar por nome` e
  `Buscar pela posição` — o par que, a 1,88:1, o crítico do ciclo 9 não conseguiu separar a 2×.
* **A Revisão a 4K é o pior vazio da janela, e a prancha não fazia jus ao tamanho dele.** Abri
  `c10_claro_3840x2160_revisao.png` inteira: as 27 linhas da fila ocupam a faixa de cima, e abaixo
  há uma folha branca contínua de ponta a ponta do painel — os 2132×1456 px que a régua conta.
  Confirmo o item aberto.
* **Uma captura mostra as três coisas ao mesmo tempo, e é a mais apertada de todas.** Em
  `c10_fita_1366x768_galeria.png` (a menor tela comum, na pele que tinha o defeito) leem-se de uma
  vez: a fita inteira sem um glifo duplicado; os dois botões de zoom **sem rótulo** entre
  `Ajustar à página` e `Tirar a caixa`, que é o item aberto; `Cancelar a varredura` acinzentado ao
  lado dos três vizinhos vivos; e o parágrafo do estado vazio terminando em **`onde parou.`** —
  duas palavras na última linha, que é o conserto da órfã, visível.
* **A fita continua certa a 4K.** Em `c10_fita_3840x2160_estudo.png`, a 3840 de largura, os 24
  botões desenham ícone e rótulo e os seis de glifo desenham só o ícone: o conserto não depende da
  largura.
* **Uma coisa que melhora a 4K e que ninguém tinha dito:** naquela mesma captura a coluna `Motivo`
  cabe inteira e lê-se sem corte nas 27 linhas. É o item 4.5 da crítica do ciclo 9
  (*"Motivo ilegível em 17 de 27 linhas a 1920"*) — ele continua aberto **a 1920**, que é onde foi
  medido, mas a largura que sobra a 4K o resolve sozinho. Não é conserto: é a mesma sobra que faz o
  painel ter 3 104,2 kpx de vazio.

---

## Como reproduzir

```bat
:: portoes -- --saida SEMPRE para benchmarks\reports\ui\c10
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONPATH=<suite>\src;<tronco>\src
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado  --pdf "...\1937 Kemeri.pdf" --saida ...\c10
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.contraste --saida ...\c10
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.progresso --saida ...\c10
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.execucao  --pdf "..." --saida ...\c10
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio  --pdf "..." --saida ...\c10   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.quadros   --pdf "..." --saida ...\c10   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.capture --marca c10 --pdf "..." --saida ...\c10
.venv\Scripts\python.exe -m pytest tests -q                                         :: 2x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly   :: no tronco, 2x

:: a pergunta de DETERMINISMO desta frente: a mesma suite sem o arquivo que le artefato
:: de outro agente (o bundle em dist\, que o agente de empacotamento reescreve)
.venv\Scripts\python.exe -m pytest tests -q --ignore=tests\integration\test_packaging.py  :: 2x

:: as duas PROVAS DE VIDA (as duas editam um arquivo do tronco e o restauram, conferindo SHA-256)
c10\c10_prova_de_vida.py    :: sem nome acessivel -> 90 acusados; glifo de volta -> 6 glifos
c10\c10_faixa_tardia.py     :: nunca troca de modo -> 4 bloqueantes; um tique de 40 ms -> 0

:: item 9 -- a janela sem torch (nao instala nem desinstala nada; bloqueia por MetaPathFinder)
.venv\Scripts\python.exe c10\c10_sem_torch.py   :: 7 de 7 ok na janela, 4 de 4 FALHOU na rede
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests\test_checkpoint.py -q  :: 27 passed

:: o portao de execucao contra as tres arvores
-m caissa.ui.audit.execucao --sabotagem ...\c10\sab_c9    :: NAO EXECUTAVEL (QtConcurrent nao existe)
-m caissa.ui.audit.execucao --sabotagem ...\c10\sab_c9x   :: 8 de 8, 4 controles calados
-m caissa.ui.audit.execucao --sabotagem ...\c10\sab_c10   :: 8 de 8, 5 controles calados

:: a regua de AST, catracas de sempre
-m caissa.ui.audit.progresso --tronco ...\critique\ui\c5\sabotado    --saida <tmp>  :: 6 de 6
-m caissa.ui.audit.progresso --tronco ...\critique\ui\c7\sab_c7      --saida <tmp>  :: 10
-m caissa.ui.audit.progresso --tronco ...\ui\c8\sab_c8               --saida <tmp>  :: 8 de 8
-m caissa.ui.audit.progresso --tronco ...\critique\ui\c9\sab_c9      --saida <tmp>  :: 1 (0 de 8)
-m caissa.ui.audit.progresso --tronco ...\critique\ui\c9\sab_c9_prog --saida <tmp>  :: p1-p4 acusam, n2 falso

:: instrumentos deste ciclo (benchmarks\reports\ui\c10\ -- so c10_prancha e c10_zoom gravam,
:: e gravam nesta pasta)
c10_icones_da_janela.py  :: 3 peles, 2 familias, 0 glifos
c10_vazio_na_tela.py     :: 3 peles x 4 larguras: 0 nao desenhados, 0 duplicados
c10_orfas.py [--sem-conserto] :: 0 de 18 orfas (6 antes, mesma regua)
c10_estado_morto.py      :: 3,66 / 3,27 / 3,66 : 1
c10_repetidos.py         :: onde mora cada nome repetido, com a cadeia de conteineres
c10_prancha.py <rotulo>  :: a prancha de contato de uma pele (24 capturas)
c10_zoom.py <png> x0 y0 x1 y1 [fator] [nome]

:: instrumentos anteriores, rodados sem alteracao (conferido antes que nao gravam)
critique\ui\c7\c7_icones_da_janela.py   :: 0 glifos nas duas peles que ele conhece
critique\ui\c7\c7_rodape_elisao.py      :: 0 ELIDE nas tres larguras
critique\ui\c7\c7_rotulos_repetidos.py  :: 2 pares divergentes
critique\ui\c7\c7_janela_pequena.py     :: minimumSize 1066x735, 0 fora
critique\ui\c5\c5_vazios.py  <png..>    :: 10 de 12 acima de 200 kpx a 1920; os seis a 4K
critique\ui\c5\c5_regioes.py <png..>    :: 73,1 % / 69,7 % / 77,4 %, vao 16 px, 114,5 kpx
ui\c8\c8_vazio_na_tela.py               :: 30 de 30 DESENHADO=sim
ui\c8\c8_barra_do_visor.py              :: ver a nota de instrumento abaixo
```

**Sobre caminhos de saída**, que já custaram 17 capturas em dois ciclos: conferi o destino de cada
script antes de rodá-lo. Os instrumentos `c5_*` e `c7_*` do crítico não gravam nada; os módulos do
arnês receberam `--saida` em toda invocação, sempre para `benchmarks\reports\ui\c10\`; as
sabotagens do detector gravaram em pasta temporária. **Nenhum arquivo de conteúdo foi escrito em
`benchmarks\reports\critique\` nem em `docs\quality\F9_CRITIQUE_*.md`.**

**Uma ressalva, e ela é minha:** rodar `progresso --tronco <árvore do crítico>` faz o interpretador
escrever `__pycache__` dentro daquelas árvores — é bytecode derivado de arquivos que eu só li, mas
apareceu lá por causa de um comando meu. Conferido: **só `.pyc`**; nenhum `.py`, `.json` ou `.md`
daquela pasta mudou. Quem rodar isso de novo deve exportar `PYTHONDONTWRITEBYTECODE=1` antes; eu
não exportei, e registro a falta.

As duas provas de vida
editam um arquivo do tronco (`qt/fita.py` e `qt/rodape.py`) e o restauram conferindo SHA-256; as
duas terminam imprimindo o hash e a palavra `confere: sim`.

**Sobre estado persistido**, que a ordem de serviço mandou tornar explícito — e aqui o ciclo achou
mais do que a pergunta pedia. A **captura** já usava estado próprio desde o ciclo 8; **os portões
não usavam**. `caissa.ui.audit.teclado`, `execucao` e os cinco instrumentos deste ciclo abriam
`JanelaPrincipal()` sem `caminho_do_estado=` -- ou seja, **liam a sessão de quem tinha aberto a
janela por último e a reescreviam ao sair**. Medido nesta sessão: o `data/app_tkinter_state.json`
do tronco foi reescrito pelos meus primeiros portões, e o instrumento de órfãs mudou de resposta
com ele (24 parágrafos com um `sash_fraction`, 18 com o declarado).

Hoje todos passam por `capture.estado_de_medicao(pasta)`, que escreve versão e
`FRACAO_DO_DIVISOR` num diretório temporário. **Conferido depois da mudança**: rodei o portão de
teclado, o censo de ícones, o de órfãs e o de estado vazio, e o `mtime` do
`data/app_tkinter_state.json` do tronco **não mudou** (13:25, de antes destas medições). Nada mais
foi escrito fora da pasta do ciclo 10 e deste documento.

**Duas notas de instrumento, para quem for reler.**

**(a)** `critique/ui/c7/c7_rodape_elisao.py` mede a elisão e **depois morre** com
`TypeError: BusyToken.update() got an unexpected keyword argument 'done'`. O argumento chama-se
`feito` em `ui/busy.py` desde a S-164, e o instrumento é do ciclo 7 -- a incompatibilidade é
anterior a este ciclo (o crítico do ciclo 9 publicou o mesmo número dele, então viu o mesmo). O
número que eu cito sai da parte que roda, e ela roda inteira:
`RotuloElidido dado=313 px, tinta=313 px, inteiro pede 313 px` nas três larguras, **0 ELIDE**.

**(b)** `c8_barra_do_visor.py` publica
`controles_visiveis_com_o_nome=0` para a pele `fita`, e isso **não** é um controle a menos na tela.
Ele compara o literal `"OCR todos diagramas"` com o `text()` do botão, e o da fita é
`"OCR todos\ndiagramas"` — o mesmo nome com a quebra que `quebrar_rotulo` põe. É a mesma armadilha
que `nomear_o_que_o_cromo_nao_desenha` normaliza desde o ciclo 8 e que este ciclo transformou num
motivo do portão de teclado. `c10_vazio_na_tela.py` normaliza o espaço em branco e mede 12 de 12
naquela pele.

---

## Nota de higiene do segundo agente

**Exportei `PYTHONDONTWRITEBYTECODE=1` em toda invocação** — é a falta que o primeiro agente
registrou logo acima, e o resultado está medido: `find benchmarks\reports\critique -name "*.pyc"`
mais novo que o início da minha passada devolve **0 arquivos**.

**O `data/app_tkinter_state.json` do tronco continua com `mtime` 13:25**, de antes de qualquer
medição desta sessão — depois de eu rodar o portão de teclado nas três peles, o censo de ícones, o
de órfãs, o de estado morto, o de contraste, o de progresso, o de execução (incluindo a janela
viva) e as duas provas de vida. Os portões usam `capture.estado_de_medicao(pasta)`, e ele segura.

**Nada foi escrito em `benchmarks\reports\critique\`, em `docs\quality\F9_CRITIQUE_*.md`, em
`packaging\` nem em `pyproject.toml`.** Os dois instrumentos do crítico que gravam no próprio
diretório rodaram a partir de cópia em pasta temporária (SHA-256 conferido antes), e os `mtime` dos
arquivos deles continuam os de 13:51/13:53. Em `packaging\` eu apenas **li** o
`pendencias\0001-torch-fora-do-escopo-de-modulo.patch`; os arquivos daquela pasta que mudaram nesta
sessão são do agente de empacotamento, que trabalhou em paralelo — e é por isso que
`tests\integration\test_packaging.py`, que reprovava três vezes na passada do primeiro agente,
**passa 53 de 53 na minha** (§Suítes).

**Nenhum teste foi afrouxado.** As duas reprovações que o item 9 criou foram tratadas uma a uma:
a de `test_checkpoint.py` foi consertada **no produto**, sem tocar no teste (§9.4a); a de
`test_field_eval.py` fica **aberta com o número**, porque a única saída que o próprio teste oferece
reescreveria dado de medição de outra frente (§9.4b).
