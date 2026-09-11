# F9 — Interface, relatório do ciclo 6

Responde ao `docs/quality/F9_CRITIQUE_C5.md`, item por item do §9. Todo número abaixo saiu de um
comando rodado nesta sessão; onde o trabalho é do agente anterior deste ciclo (que caiu num limite
de taxa em "Now let me run the gates"), está dito **quem fez**.

**Duas mãos neste ciclo.** O agente anterior escreveu o código dos itens 1, 2, 4 e 5 e capturou as
36 telas; ele não chegou a rodar portão nenhum e não escreveu relatório. Eu rodei todos os portões,
abri as 36 capturas, achei **dois defeitos que a medição não tinha pegado** — um deles é o item 2
sobrevivendo ao próprio conserto —, consertei os dois com prova de vida, alarguei o detector do
item 3 contra uma sabotagem nova minha, e recapturei as 36 na fonte do produto.

---

## Resumo por item do §9

| # | item | número medido | veredito |
|---|---|---|---|
| 1 | cor própria para a dica do campo | **7,08:1** claro e **7,95:1** escuro no `grab()`; **3,96:1** sem a declaração | **FECHADO**, agora também no pixel |
| 2 | `"Ler página"` nomeia controle inexistente | **0** nomes citados fora da tela, nas duas peles | **FECHADO** — e ele tinha **reaberto** |
| 3 | detector de thread fraco | **6 de 6** na sabotagem do crítico, **8 de 8** na minha | **FECHADO**, com duas provas de vida |
| 4 | uma grade de ícones só | caixa **16×16 em 9 de 9** (era 5 caixas); tinta **34,0 %–53,1 %** | **METADE**: caixa fechada, tinta **ABERTA** |
| 5 | capturar na fonte do produto | `QFontInfo` = **`Segoe UI`**, `confere=sim`, censo refeito | **FECHADO** |
| 6 | vazio de tela grande | **10 de 12** acima de 200 kpx a 1920; **0 de 12** a 1366 e a 1280 | **ABERTO** |
| 7 | ocupação contra o painel | **73,6 %** (claro) e **70,2 %** (escuro) a 1920, régua do crítico | medida **FECHADA**, leiaute **PARCIAL** |

Além do §9, dois defeitos que **só o olho achou** e que este ciclo fechou: o campo da FEN mostrando
o fim em vez do começo a 1280, e o estado vazio citando um nome que só existe no catálogo.

---

## Portões — todos rodados, na ordem da carta §6

| portão | comando | resultado |
|---|---|---|
| Contraste WCAG AA | `caissa.ui.audit.contraste` | **296 pares / 218 sob portão / 0 reprovados** nas duas peles. Menor folga: **3,27:1** (marcação PROBLEMA sobre casa escura) e **3,03:1** (`QScrollBar::handle`), piso 3,0. **PASSOU** |
| Teclado + nome + papel | `caissa.ui.audit.teclado` | 24+52+30+39+21+50 = **216 focáveis**, todos alcançados pelo Tab, ciclo fecha, **0** sem nome, **0** sem papel, **0** nome vazio. **PASSOU** |
| Progresso | `caissa.ui.audit.progresso` | **8** indicadores; **13** operações de fundo em `qt/`, **0 invisíveis**. **PASSOU** |
| Nada bloqueia > 16 ms | `caissa.ui.audit.bloqueio` ×3 | **REPROVOU**, 6–7 operações violam nas três execuções. Medianas de 3: abrir PDF **182,6 ms**, p.121 **81,2**, p.41 **82,3**, p.42 **79,1**, rasterizar **58,1**, aba Dataset **14,0**, aba Galeria **15,4**. Atribuição por família, numa quarta execução com `--execucoes 1`: **desta frente 1,1 % a 2,0 %** (1,6–2,5 ms) — a causa é PyMuPDF, como no ciclo 5 |
| fps ≥ 55 @ p95 | `caissa.ui.audit.quadros` ×3 | juntos **99,0 · 101,4 · 107,6** → mediana **101,4 fps**; pan 711–757, zoom 73,4–76,2. **PASSOU** (84 % de folga) |
| Sobreposição / fora da janela | `critique/ui/sobreposicao.py` | `minimumSizeHint` **1066×735**; **0** controles fora; **1** sobreposição de 987 px² (o `QLineEdit` interno do `QSpinBox`, isenta), igual com título de 149 chars |
| Ocupação / vazio | `c5_regioes.py`, `c5_vazios.py` do crítico, sobre as 36 novas | itens 6 e 7, abaixo |
| Rodapé (barra × Cancelar) | `c6_rodape.py` sobre as 36 | **8 ociosas, 28 ocupadas, 0 contradições**; face do Cancelar separada nas duas peles |

**Suítes.** Nossa: **2989 passed, 1 skipped, 0 failed** em 565 s (a base era 2987/1/0; os 2 a mais
são meus testes do item 3). Tronco, `-p no:randomly`: **4447 passed, 3 failed, 2 skipped, 4382
subtests passed** em 263 s. As **três reprovações são as três de sempre**, pelo nome —
`test_docs::test_a_arvore_do_README_lista_todo_modulo_do_pacote`,
`test_editor_model::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter` e
`test_strings::test_no_ui_string_uses_an_unaccented_portuguese_word` — e conferi que a terceira
acusa `biblioteca.py` e `substituicao.py`, arquivos que ninguém deste ciclo tocou.

---

## Item 1 — a dica do campo (o bloqueante). **FECHADO**, e agora o número vem do pixel

**Feito pelo agente anterior**, as duas metades que o §9.1 pediu:
`chess_diagram_ocr/ui/folha_de_estilo.py` declara `placeholder-text-color` para os dez seletores
(linhas ~511 e ~515) e o papel `PlaceholderText` entrou em `PAPEIS_DA_PALETA`;
`src/caissa/ui/audit/contraste.py` ganhou `cor_e_alfa()` e `compor()`, com `ALFA_DA_DICA = 128`
documentado. Quatro testes cobrem isso em `tests/unit/ui/test_contraste.py`, entre eles a prova de
vida `test_o_portao_reprova_quando_a_declaracao_da_dica_some`, que apaga a declaração e exige
**3,96:1**.

**Feito por mim: a metade que faltava.** O alvo do crítico tinha duas réguas — *"no relatório do
arnês **e** `≥ 4,5:1` medido no `grab()` de um `QLineEdit` habilitado com dica, porque o número tem
de vir do pixel"*. O arnês estava coberto; **nenhum teste olhava um pixel desenhado**. Escrevi
`tests/test_qt_tema.DicaDoCampoNoPixelTests` no tronco (é onde o Qt mora), que constrói o campo
habilitado, aplica o tema e mede a razão no `grab()`:

```
  pele claro : tinta=(85, 85, 85)    fundo=(248, 249, 251)  razao=7.08:1
  pele escuro: tinta=(167, 173, 182) fundo=(21, 23, 26)     razao=7.95:1
  SEM a declaracao (o estado do ciclo 5): tinta=(124, 124, 125) fundo=(248, 249, 251)  razao=3.96:1
```

A última linha é a prova de vida, e ela **reproduz o pixel do crítico ao centésimo**: ele
fotografou `rgb(124, 124, 126)` e publicou 3,96:1. O teste cobra o valor exato, não só "abaixo do
piso".

**Duas vezes o teste estava cego, e as duas foram achadas por rodá-lo sabotado.** Primeiro apagar
só a regra da folha ainda dava 7,08:1 — o papel `PlaceholderText` entrou na `QPalette` no mesmo
conserto e sozinho já pinta a dica opaca, então a sabotagem tem de tirar as duas metades. Depois,
com as duas fora, a medida deu **19,23:1** com tinta `(7, 6, 4)`: um `QLineEdit` mostrado sozinho
recebe o foco e desenha o **cursor de texto**, uma barra preta de 1×20 px que ganha da dica na
conta de "o pixel mais afastado do fundo". Sem `show()` e com recuo de 6 px na moldura, a medida
passou a ser a dica.

**Na captura publicada**, com o campo *desabilitado* (a leitura do dataset ainda correndo, que é o
que as 36 mostram): **6,54:1** na clara e **7,14:1** na escura.

---

## Item 2 — o estado vazio nomeia um controle que existe. **FECHADO — e ele tinha reaberto**

**O agente anterior** trocou o literal `"Ler página"` por `comandos.rotulo("ler_pagina")` e
escreveu três testes de cruzamento em `tests/test_ui_comandos.EstadoVazioNomeiaControleQueExisteTests`.
Todos verdes. **E a tela continuou sem o nome.**

Isso apareceu **abrindo a captura**, não medindo. A frase passou a dizer *"Ler esta página"*, e uma
sonda no produto vivo devolve:

```
  -- ANTES do conserto (a dica vem inteira; a quebra de linha e' a tecla)
  pele classica: QPushButton texto=''                    nomeAcessivel='Ler esta página'  dica='Ler esta página\nTecla: Ctrl+R'
  pele foco:     QPushButton texto='OCR todos diagramas' nomeAcessivel=''                 dica='Ler esta página\nTecla: Ctrl+R'
                 QPushButton texto=''                    nomeAcessivel='Ler esta página'  dica='Ler esta página\nTecla: Ctrl+R'

  -- DEPOIS
  pele classica: QPushButton texto=''                    nomeAcessivel='Ler esta página'  dica='OCR todos diagramas — Ler esta página\nTecla: Ctrl+R'
  pele foco:     QPushButton texto='OCR todos diagramas' nomeAcessivel=''                 dica='Ler esta página\nTecla: Ctrl+R'
                 QPushButton texto=''                    nomeAcessivel='Ler esta página'  dica='OCR todos diagramas — Ler esta página\nTecla: Ctrl+R'
```

**Zero controles visíveis mostram "Ler esta página" como texto legível.** Na Foco a pílula mostra
"OCR todos diagramas"; na clássica o botão é só-de-ícone e não mostra nada. É o defeito do §7.1 do
ciclo 5 inteiro, com o literal trocado — e o portão do catálogo ficava verde porque *"Ler esta
página"* é, sim, um rótulo declarado. **Um catálogo não é uma tela.**

**Conserto, e ele é o que o crítico prescreveu com todas as letras:**

* `qt/painel_de_resultado.MENSAGEM_VAZIA` passa a citar `comandos.rotulo_de_botao("ler_pagina")` —
  "OCR todos diagramas", o texto que o botão mostra. (O §9.2 pedia `rotulo_curto`; o agente anterior
  usou `rotulo`.)
* `qt/painel_do_pdf._dica_do_comando` põe o nome do botão na dica do botão só-de-ícone, que é o
  único canal visual que sobra na pele clássica: `"OCR todos diagramas — Ler esta página"`. O rótulo
  por extenso não some — fica na mesma dica e no `accessibleName`, que é o que o leitor de tela
  anuncia (F9-C2).
* A regra é `_e_outro_nome`, e ela é estreita de propósito: só prefixa quando o rótulo do botão é um
  **nome diferente**, não um glifo nem um encurtamento. **A primeira versão não era**, e isso saiu
  de reler o `c5_casos.py` depois da mudança: ela produzia `"- — Diminuir o zoom da página"` nos
  dois botões de zoom e repetia `"Tirar a caixa"` antes de `"Tirar a caixa do diagrama
  selecionado"`. Hoje **um único** botão da barra ganha a dica de dois nomes, que é o único com dois
  nomes sem uma palavra em comum.

**O portão novo: `tests/test_qt_janela.EstadoVazioNaTelaTests`.** Abre a janela nas duas peles,
percorre as seis abas somando o que cada uma mostra, e cobra todo nome entre aspas das três
mensagens de estado vazio contra o `text()` de um controle **visível** ou a primeira linha da dica
dele. `accessibleName` não vale: ele é para quem ouve, e a frase que se lê manda procurar com os
olhos.

**Prova de vida — e ela reprovou o portão antes de aprovar o conserto.** Devolvi a `MENSAGEM_VAZIA`
para o rótulo do menu e rodei os dois portões:

```
  o portao NOVO (a tela)    : AssertionError: Lists differ: [] != [('qt/painel_de_resultado.MENSAGEM_VAZIA', 'Ler esta página')]
                              SUBFAILED(pele='classica')   -> 1 failed, 2 passed
  o portao ANTIGO (catalogo): 3 passed
```

O portão antigo **passa com o defeito na tela**. Era ele, sozinho, que segurava o item 2.

**A primeira versão do portão novo também era cega, e a prova de vida a pegou.** A varredura lia a
dica inteira e partia no travessão, guardando **as duas** metades — com isso "Ler esta página"
continuava no conjunto e a sabotagem passava em verde. Um portão que aceita os dois nomes do mesmo
comando não cobra nenhum. Hoje ele guarda só o que vem antes do travessão, e há um teste de
controle que afirma o que a varredura deve conter **e o que não**.

**Medida final**, `c6_estado_vazio.py` sobre o produto vivo:
`nomes citados que nao existem em nenhuma pele: 0`, com os três citados sendo
`'Achar no texto…'`, `'Ler folha'` e `'OCR todos diagramas'`.

---

## Item 3 — o detector de thread. **FECHADO: 6 de 6 e 8 de 8**

**O agente anterior** reescreveu `caissa.ui.audit.progresso` e o gêmeo dele em
`tronco/tests/test_busy.py`: `CLASSES_DE_THREAD` compara o **último termo** do nome,
`classes_de_thread` cresce por **herança** em ponto fixo, `METODOS_DE_SUBMISSAO` pega a submissão a
um pool já aberto, e `_prova_de_registro` exige um `register` num receptor de ocupação ou com a
assinatura do `BusyRegistry` — não mais qualquer nome contendo `registrar`.

**Rodei a cópia sabotada do próprio crítico**, sem tocá-la (saída para pasta minha):

```
DEFEITOS BLOQUEANTES (6): total conhecido com barra indeterminada, ou operacao de fundo invisivel
  - LeitorSabotador.a_forma_que_o_portao_conhece   INVISIVEL (constroi threading.Thread)
  - LeitorSabotador.b_import_direto                INVISIVEL (constroi Thread)
  - LeitorSabotador.c_pool                         INVISIVEL (submete por ThreadPoolExecutor(...).submit)
  - LeitorSabotador.d_timer                        INVISIVEL (constroi threading.Timer)
  - LeitorSabotador.e_subclasse                    INVISIVEL (constroi _MinhaThread)
  - LeitorSabotador.f_registro_de_mentira          INVISIVEL (constroi threading.Thread)
```

**6 de 6**, e nenhuma marcada como REGISTRADA. O alvo do §9.3 está batido.

**Mas um portão que só passa na sabotagem que o motivou não foi testado, foi ajustado.** A ordem de
serviço mandou plantar a minha. Escrevi **oito formas novas** contra o detector já alargado e rodei:
**três passaram**.

| forma | antes | depois |
|---|---|---|
| `from threading import Thread as T` + `T(...)` | **não aparece** | INVISIVEL |
| `class _Derivada(T)` + `_Derivada().start()` | **não aparece** | INVISIVEL |
| `QThreadPool.globalInstance().start(tarefa)` | **não aparece** | INVISIVEL |
| `import threading as th` + `th.Thread(...)` | INVISIVEL | INVISIVEL |
| `multiprocessing.Process(...)` | INVISIVEL | INVISIVEL |
| `ProcessPoolExecutor(1).submit(...)` | INVISIVEL | INVISIVEL |
| `asyncio.get_event_loop().run_in_executor(...)` | INVISIVEL | INVISIVEL |
| `self._mapa.registrar(...)` ao lado de thread crua | INVISIVEL | INVISIVEL |

As duas primeiras passavam pelo **apelido de import**: o termo final de `T(...)` é `T`, e a herança
segue o nome da base, que também é `T`. A terceira passava porque `QThreadPool.start` não constrói
classe nenhuma no ponto de chamada e não se chama `submit`.

**Conserto**: `apelidos_de_thread()` resolve `import ... as ...` por arquivo e entra no termo final
e nas bases de classe; `RECEPTORES_DE_POOL` aceita `.start(...)` **com argumento** num receptor com
nome de pool. `start` não pode entrar em `METODOS_DE_SUBMISSAO`: `qt/` tem dezenas de
`self._relogio.start(250)` e todo `Tarefa(...).start()` é a partida de uma thread que a regra de
construção já contou — somá-la de novo infla o placar. Há teste dos dois lados: as oito formas têm
de aparecer, e `self._relogio.start(250)`, `self._animacao.start()` e `self._pool.start()` têm de
**não** aparecer.

```
=== SABOTAGEM C6 (8 formas minhas) ===
DEFEITOS BLOQUEANTES (8)
=== TRONCO REAL ===
Operacoes de fundo em qt/ (13) — Nenhum defeito bloqueante de progresso.
```

**8 de 8 na sabotagem, e o tronco real intacto**: as mesmas 13 operações, 0 invisíveis. O mesmo
alargamento foi para `tronco/tests/test_busy.py`, que compartilha a régua — era o ponto cego que o
crítico nomeou (*"o teste e o portão compartilham o ponto cego"*) — com a sabotagem C6 replicada lá
(`SABOTAGEM_C6`) e o mesmo par de testes.

---

## Item 4 — uma grade de ícones só. **METADE FECHADA, e digo qual metade**

**Feito pelo agente anterior**: `ui/icones.na_grade()` põe todo desenho na mesma grade — o lado
maior enche a caixa, escala **isotrópica**, centrado. `c6_icones.py` mede no produto vivo, no
tamanho que o botão usa:

```
  botao                                            botao  icone     caixa   tinta  tinta/caixa
  Ler esta página                             42x26       16   16x16       120        46.9 %
  Tirar a caixa do diagrama selecionado       42x26       16   16x16        87        34.0 %
  Selecionar área para ler                    42x26       16   16x16       108        42.2 %
  Página anterior                             42x26       16   16x16        96        37.5 %
  Próxima página                              42x26       16   16x16        90        35.2 %
  Diminuir o zoom da página                   42x26       16   16x16       106        41.4 %
  Aumentar o zoom da página                   42x26       16   16x16       113        44.1 %
  Ajustar à largura                           42x26       16   16x16        93        36.3 %
  Ajustar à página                            42x26       16   16x16       136        53.1 %

  caixas de glifo distintas: [(16, 16)]   amplitude: 0 px de largura, 0 px de altura  (alvo <= 1)
  tinta/caixa de 34.0 % a 53.1 %  -> amplitude relativa 43.9 %  (alvo <= 20 %)
  botoes so-de-icone sem desenho declarado: 0
```

**Caixa: FECHADA.** Eram cinco caixas (14×10, 14×8, 12×14, 12×12, 11×11) mais um `×` que era um
caractere de texto de **4×5 px** num botão de 26 px; hoje são **9 de 9 em 16×16**, amplitude 0 px, e
**0** botões só-de-ícone sem desenho declarado — o `×` de texto deixou de existir.

**Tinta: ABERTA, e não vou dizer que não está.** 34,0 % a 53,1 %, amplitude relativa **43,9 %**
contra o alvo de ±20 %. A razão entre o mais sólido e o mais fino caiu de **2,15×** (65,7/30,6) para
**1,56×**, mas o alvo do §9.4 pede os dois números e só um chegou. Fechar o segundo é redesenhar
glifo — o peso do traço é declarado uma vez e não por ícone, de propósito —, e não foi feito neste
ciclo. **Item 4 continua aberto na tinta.**

---

## Item 5 — capturar na fonte do produto. **FECHADO**

**Feito pelo agente anterior**: `caissa.ui.audit.capture.impor_a_fonte_do_produto` força
`QFont("Segoe UI", 9)` **antes** de qualquer janela — antes porque `tema.fonte_base()` lê
`QApplication.font()` na construção do primeiro painel —, confere com `QFontInfo(...).family()`,
grava o manifesto ao lado dos PNGs e grita no `stderr` se não conferir. **Recapturei as 36 depois
dos meus consertos**, e o manifesto diz:

```json
{ "plataforma": "offscreen", "familia_do_produto": "Segoe UI",
  "familia_antes": "Alef", "familia_resolvida": "Segoe UI", "confere": "sim" }
```

**A segunda metade do item — "re-report the census honestly" — é minha.** O `c5_tipos.py` do crítico
usa `os.environ.setdefault`, então ele mede em Alef mesmo quando se pede o contrário. Copiei-o para
`benchmarks/reports/ui/c6/c6_tipos.py` com **uma** mudança: chamar `impor_a_fonte_do_produto` antes
de `aplicar_tema`. Censo refeito, 18 combinações de pele × tamanho × aba:

* `PEDIDO` e `RESOLVIDO` são **idênticos em todas as 18** — nenhum papel é degradado pela
  substituição de família. O maior combo vai de **50,5 % a 64,5 %** dos controles visíveis; o pior
  caso (Galeria, 64,5 %) é o mesmo que o crítico publicou, agora honesto.
* Os cinco papéis resolvem no que pedem: TITULO 12 pt/700, CORPO 9 pt/400, ACAO 9 pt/600, AUXILIAR
  8 pt (resolve 8,2), DADO `Consolas` 9 pt.

**E confirmo a ressalva do crítico contra ele mesmo**, rodando o `c5_peso.py` dele na plataforma
real (sem `QT_QPA_PLATFORM` no ambiente — com ela o modo `real` não toma efeito):

```
  Varrer o livro            CORPO x ACAO   tinta 132 -> 150 ( +13.6 %)
  Corrigir agora            CORPO x ACAO   tinta 167 -> 176 (  +5.4 %)
  Copiar headers para todos CORPO x ACAO   tinta 306 -> 333 (  +8.8 %)
  Marcar revisado           CORPO x ACAO   tinta 189 -> 214 ( +13.2 %)
```

**+5,4 % a +13,6 %** em Segoe UI, contra +27 % a +37,2 % que a mesma régua dá em Alef. O eixo de
peso 600 é **fraco no produto real**, e qualquer leitura que o chame de forte está lendo Alef. O
eixo que funciona é o TITULO: **+194,8 % a +214,4 %** de tinta.

Uma honestidade a mais: o `c6_tipos.py` roda `offscreen` **com a família forçada**, e ali o mesmo
eixo dá +19,0 % a +24,1 %. A tinta de base bate com a real (306 contra 305; 132 contra 131) — a
família e as métricas estão certas —, mas o **rasterizador** do offscreen não é o da plataforma
nativa. Para largura e layout a captura serve; para fração de tinta, o número que vale é o da
plataforma real, acima.

---

## Item 6 — vazio de tela grande. **ABERTO**

`c5_vazios.py` do crítico (maior retângulo vazio **exato**) sobre as 36 novas capturas:

| painel (1920×1080) | claro | escuro |
|---|---|---|
| Texto | **421,8 kpx** (1044×404) | **405,1 kpx** |
| Revisão | **391,0 kpx** (1040×376) | **357,8 kpx** |
| Dataset | **367,5 kpx** (1044×352) | **350,8 kpx** |
| Estudo | **270,9 kpx** (408×664) | **257,9 kpx** |
| Galeria | **222,9 kpx** (796×280) | **207,0 kpx** |
| Resultado | 115,8 kpx | 132,9 kpx |

**10 de 12 acima de 200 kpx a 1920** — eram 11 de 12 no ciclo 5; hoje o Resultado está abaixo do
piso nas **duas** peles. **A 1366×768 e a 1280×800: 0 de 12**, confirmado nas 24 capturas.

Os três maiores estão nos mesmos números do ciclo 5 (421,8 / 391,0 / 367,5 contra 421,8 / 391,0 /
371,7). **Nada foi feito contra este item neste ciclo**, e o alvo do §2.4 — nenhuma região acima de
200 kpx com menos de 2 % de tinta — continua reprovando a 1920. É o único dos nove critérios que não
passa, e continua sendo.

Vendo as capturas, o vazio é sempre a mesma forma: corpo de tabela sem linhas (Revisão, 27 de N
linhas; Dataset, tabela vazia durante a leitura) ou estado vazio centrado num painel de 1044 px de
largura (Texto). Nenhuma das três é largura mal usada — é **altura** reservada para dado que não
chegou.

---

## Item 7 — ocupação contra o painel. **A medida está fechada; o leiaute, parcial**

`c5_regioes.py` do crítico, sem uma linha alterada, sobre as 36 novas:

| captura | vão tabuleiro→paleta | à direita da paleta (0 % de tinta) | ocupação **contra o painel** |
|---|---|---|---|
| claro 1920 | **16 px** | 159×690 = **109,7 kpx** | **73,6 %** |
| escuro 1920 | **16 px** | 191×658 = 125,7 kpx | **70,2 %** |
| claro 1366 | 16 px | 135×402 = 54,3 kpx | 64,3 % |
| claro 1280 | 16 px | 145×430 = 62,4 kpx | 64,9 % |
| escuro 1366 | 16 px | 167×370 = 61,8 kpx | 59,2 % |
| escuro 1280 | 16 px | 176×399 = 70,2 kpx | 60,2 % |

**A régua é a do crítico e não mudou entre os ciclos** — é o mesmo script, e ele mede
`tabuleiro / [largura do painel × altura do tabuleiro]`, não uma caixa que termina na borda da
paleta. Contra ela: **73,6 %** hoje, contra os **59,4 %** que ele publicou. O vão continua em
**16 px** (era 203 px antes do ciclo 5).

**O que ainda não fechou**: os **109,7 kpx** de tinta zero à direita da paleta. Eram 159,5 kpx no
ciclo 5, então caíram **31 %**, mas não sumiram — e o crítico está certo de que o número honesto é
esse, e não a ocupação numa caixa que termina onde a emptiness começa. **Publico os dois lados: a
ocupação subiu de verdade e o poço morto encolheu de verdade, e ele ainda existe.**

Um aviso para o próximo ciclo: `c6_medidas.py` (do agente anterior) publica um terceiro número,
`ocupacao_no_painel = 45,6 %` a 1920 — é **área/área** contra o painel inteiro, incluindo cabeçalho
e rodapé do painel, enquanto o do crítico é **largura/largura** com a mesma altura. Os dois são
defensáveis e não são comparáveis. **O número desta frente é o do crítico**, 73,6 %, porque ele é o
que não muda entre ciclos.

---

## Os dois defeitos que só o olho achou

A ordem de serviço diz que olhar achou, em todo ciclo, o que a medição não pegou. Aconteceu de novo,
duas vezes.

### A. O campo da FEN mostrava o **fim** da FEN a 1280×800

`c6_claro_1280x800_estudo.png`, ampliado 3×, mostrava:

```
qkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
```

**As três primeiras casas somem — `rnb` — sem reticência e sem nenhum sinal.** `QLineEdit.setText`
deixa o cursor no fim e o campo rola para o fim; a 1920 o campo cabe inteiro e nada disso aparece.
Nenhuma medida pegava: não há rótulo espremido, não há controle fora da janela, não há cabeçalho
elidido — só texto rolado. Quem lê a FEN na tela para copiar a mão copia uma **FEN inválida**.

Conserto: `painel_de_estudo._mostrar_fen_do_comeco()` (e a mesma linha em `painel_de_resultado`)
põem o cursor em 0 depois de escrever. O começo vale mais que o fim: `rnbqkbnr/...` é a colocação
das peças, e o rabo `w KQkq - 0 1` é o mesmo em quase toda posição de abertura.

**A régua do teste é o pixel, não o cursor.** `QLineEdit.cursorPositionAt(QPoint(4, h/2))` responde
qual caractere está **desenhado** na borda esquerda de dentro do campo — afirmar
`cursorPosition() == 0` mediria a intenção. Prova de vida, com a chamada removida:

```
  AssertionError: 0 != 35 : o campo esta desenhando o FIM da FEN ... ve-se 'RNBQKBNR w K'
  AssertionError: 0 != 37 : rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1
```

Na recaptura, `c6_claro_1280x800_estudo.png` mostra `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w
KQkq - `.

### B. O item 2 tinha reaberto

Está contado inteiro acima. Registro aqui só o padrão, porque é o mesmo pela sexta vez nesta frente:
**um instrumento afirmando o que a tela não contém**. Desta vez o instrumento era um teste novo,
escrito neste mesmo ciclo, para fechar exatamente este defeito.

---

## O que continua aberto, com o número

| # | item | número |
|---|---|---|
| 4 (tinta) | ícones com tinta de **34,0 % a 53,1 %**, amplitude relativa **43,9 %** contra alvo de ±20 % | medido hoje |
| 6 | **10 de 12** painéis acima de 200 kpx a 1920 (Texto 421,8; Revisão 391,0; Dataset 367,5) | medido hoje |
| 7 (leiaute) | **109,7 kpx** de tinta zero à direita da paleta a 1920 claro | medido hoje |
| 8 | coluna "Motivo" com 695 px a 1920: **17 de 27** linhas não cabem; 383 px a 1366 e 335 px a 1280: **25 de 27** nas duas | medido hoje |
| 10 | o Dataset mostra **as duas frases ao mesmo tempo**, nas seis combinações de pele × tamanho: `'Lendo o dataset'` no centro do painel e `'leitura do dataset (5431 amostra(s))'` no rodapé | medido hoje |
| 11 | aba Estudo com **29 botões** no topo, em **4 filas** a 1920 e **5 filas** a 1366 e a 1280, nas duas peles, contra o alvo de ≤ 12 em ≤ 2; a pele Foco duplica "Aplicar a FEN digitada" e "Salvar a posição" entre as pílulas e o painel | medido hoje |
| — | `bloqueio` reprova em 6–7 operações, com **1,1 %–2,0 %** desta frente e o resto em PyMuPDF | medido hoje |

---

## O que mudou, arquivo a arquivo

**Nossa suíte**

* `src/caissa/ui/audit/progresso.py` — `apelidos_de_thread`, `RECEPTORES_DE_POOL`,
  `_termo_final(no, apelidos)`, `forma_de_fundo(no, classes, apelidos)`, resolução de apelido nas
  bases de classe.
* `tests/unit/ui/test_medicao.py` — `test_as_oito_formas_do_ciclo_6_tambem_sao_vistas` e
  `test_o_start_de_um_relogio_nao_e_operacao_de_fundo`.
* `benchmarks/reports/ui/c6/c6_tipos.py` — censo tipográfico na fonte do produto (novo).
* `benchmarks/reports/ui/c6/*.png` — as 36 recapturadas em `Segoe UI`, com manifesto.

**Tronco** (`chess_diagram_ocr/`)

* `qt/painel_de_resultado.py` — `MENSAGEM_VAZIA` cita `rotulo_de_botao`; cursor da FEN em 0.
* `qt/painel_do_pdf.py` — `_e_outro_nome`, `_dica_do_comando`.
* `qt/painel_de_estudo.py` — `_mostrar_fen_do_comeco`.
* `tests/test_busy.py` — régua alargada (apelidos, `RECEPTORES_DE_POOL`), `SABOTAGEM_C6` e 2 testes.
* `tests/test_qt_janela.py` — `EstadoVazioNaTelaTests` (2 testes).
* `tests/test_qt_tema.py` — `DicaDoCampoNoPixelTests` (2 testes).
* `tests/test_qt_painel_de_estudo.py` — 2 testes do campo da FEN.
* `tests/test_qt_painel_do_pdf.py` — `DicaDoBotaoSoDeIconeTests` (5 testes).
* `tests/test_ui_comandos.py` — a asserção passa a cobrar o rótulo **do botão**, com o motivo
  escrito; `tests/test_qt_janela` cobra o outro lado, contra a tela.

**Nada foi afrouxado.** A única asserção reescrita é a do `test_ui_comandos` acima, e ela mudou de
alvo — do rótulo do menu para o rótulo do botão — junto com um portão **novo e mais estrito** que
cobra o mesmo nome contra o pixel da tela e que **reprova** com o código anterior.

---

## Como reproduzir

```bat
:: portoes
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m caissa.ui.audit.contraste --saida benchmarks\reports\ui\c6
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --saida benchmarks\reports\ui\c6
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONPATH=<suite>\src;<tronco>\src
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.teclado  --pdf "...\1937 Kemeri.pdf" --saida ...\c6
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.bloqueio --pdf "...\1937 Kemeri.pdf" --saida ...\c6   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.quadros  --pdf "...\1937 Kemeri.pdf" --saida ...\c6   :: 3x
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m caissa.ui.audit.capture  --marca c6 --pdf "...\1937 Kemeri.pdf" --saida ...\c6
..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly   :: no tronco

:: sabotagens (as duas gravam em pasta temporaria, nunca sobre as capturas)
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco benchmarks\reports\critique\ui\c5\sabotado --saida <tmp>   :: 6 de 6
.venv\Scripts\python.exe -m caissa.ui.audit.progresso --tronco <tmp>\sab_c6 --saida <tmp>                                 :: 8 de 8

:: instrumentos deste ciclo (benchmarks\reports\ui\c6\ -- nenhum grava arquivo)
c6_estado_vazio.py   :: 0 nomes citados fora da tela
c6_icones.py         :: caixa unica 16x16, tinta 34,0 %-53,1 %
c6_tipos.py          :: censo PEDIDO x RESOLVIDO em Segoe UI
c6_medidas.py        :: tabuleiro, tabelas e vazio de painel na janela viva
c6_rodape.py <png..> :: 8 ociosas, 28 ocupadas, 0 contradicoes
c6_aberto.py         :: os itens 8, 10 e 11 na janela viva -- 17/25/25, duas frases, 29 botoes

:: instrumentos do critico, rodados sem alteracao (nenhum grava arquivo -- conferido antes)
critique\ui\sobreposicao.py         :: 1066x735, 0 fora, 1 sobreposicao isenta
critique\ui\c5\c5_vazios.py  <png..>  :: maior retangulo vazio exato
critique\ui\c5\c5_regioes.py <png..>  :: vao de 16 px, ocupacao 73,6 % contra o painel
critique\ui\c5\c5_casos.py            :: 0 espremidos, 0 cabecalhos cortados, 'Ler pagina' = 0 controles
critique\ui\c5\c5_peso.py real        :: +5,4 % a +13,6 % em Segoe UI  (SEM QT_QPA_PLATFORM no ambiente)
```

Os três números do "continua aberto" que não vinham de instrumento publicado — `Motivo` cortado, as
duas frases do Dataset, as filas do Estudo — estão em `c6_aberto.py`, que **não grava nada** e roda
contra a janela viva com `impor_a_fonte_do_produto` aplicada, a mesma fonte das capturas (medir
largura de texto em Alef mediria outra tipografia). A régua do `Motivo` é
`fontMetrics().horizontalAdvance(texto)` contra `columnWidth(col) - 8`: o texto pedindo mais largura
do que a coluna tem.

**Sobre caminhos cravados**, que já custaram 17 capturas em dois ciclos: conferi o destino de cada
script antes de rodar. Os sete instrumentos `c5_*` e o `sobreposicao.py` **não gravam nada**; os
módulos do arnês têm todos `--saida` e eu o passei sempre. Os quatro que gravam com caminho cravado
— `casos_ruins.py`, `estados.py`, `titulo_longo.py`, `c3/colapso_foto.py` — **não foram rodados**.
As duas sabotagens gravaram em pasta temporária, e a cópia sabotada do crítico foi lida, nunca
escrita.

**Um defeito no instrumento do crítico, para registro e sem conserto meu** (não posso tocar
`benchmarks/reports/critique/`): `c5_casos.py` levanta `AttributeError: 'Comando' object has no
attribute 'nome'` na seção 7. As seções 1 a 6 rodam e são as que este relatório cita.
