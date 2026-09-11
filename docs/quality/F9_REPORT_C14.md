# F9 — Interface, relatório do ciclo 14

```
CICLO: 14
FRENTE: F9 (Interface)
BLOQUEANTE DO CICLO 13: fechado nas duas metades — o produto e o instrumento
```

O ciclo 13 reprovou por **uma** coisa: na densidade **Compacta**, 6 de 6 títulos de `QGroupBox` da
janela principal eram pintados com até **8 dos seus 21 px debaixo do primeiro filho do próprio
grupo**. `Lances`, `Comentário do lance` e `Filtros` chegavam à tela com a metade de baixo de cada
letra apagada, nas três peles, e estava fotografado desde o ciclo 10 sem que régua nenhuma o
visse — porque **toda régua desta frente perguntava a medida do texto a `QWidget.fontMetrics()` e
a tela pinta a fonte da folha de estilo**.

As duas metades estão fechadas, e a segunda é a que importa: existe agora uma régua que lê a folha.

| o que | onde | hoje |
|---|---|---|
| **título de grupo com tinta coberta** | 3 peles × 2 densidades × 4 larguras | **0 de 6**, nas 24 combinações |
| **a régua que era cega** | `caissa.ui.audit.texto_pintado` | 564 textos pintados medidos, **24 cegos** (a folha pinta outra fonte que a do widget — eram **84** antes do item 2), **0 cobertos, 0 cortados**. PASSOU |
| **prova de que ela deixou de ser cega** | a mesma régua com a faixa de antes | **6 de 6 na compacta, 3 de 6 na confortável**, `Lances` 8 px, `Comentário do lance` 8 px, `Filtros` 8 px, `Cabeçalhos do PGN` 5 px, `Este diagrama` 5 px, `Reconhecido…` 3 px — os seis nomes e os seis números do §3 da crítica, à unidade |
| **as fotografias, olhadas** | `benchmarks/reports/ui/c14/capturas/` | par ANTES/DEPOIS por grupo, mesma pele, mesma densidade, mesma largura, mesmo recorte |

---

## §1 — O bloqueante, pelas duas metades

### 1.1 O produto: a faixa do título sai da **mesma escala** que o pinta

O defeito era duas linhas do mesmo arquivo lendo escalas diferentes:

```python
ui/folha_de_estilo.py:340   QGroupBox      { margin-top: espaco.linha()px }   # 4 px compacta
ui/folha_de_estilo.py:377   QGroupBox::title { font-size: 12pt; bold }        # 21 px pintados
```

Um token de **espaçamento** reservando o lugar de um degrau da **escala tipográfica**. Os dois
números não tinham como se encontrar; o Qt punha o quadro do grupo a 4 px do topo, o primeiro
filho subia até lá, e o que sobrava do título saía debaixo dele.

**O conserto não é o número, é a fonte do número.** Hoje:

```python
titulo_em_pontos = tipografia.escala(base)[PAPEL_PINTADO["QGroupBox::title"]]
faixa_do_titulo  = altura_do_titulo or tipografia.altura_do_texto(titulo_em_pontos)
QGroupBox { margin-top: {faixa_do_titulo}px }
```

Três peças novas, e cada uma fecha um jeito de a deriva voltar:

1. **`ui/folha_de_estilo.PAPEL_PINTADO`** — `seletor da folha -> degrau da escala com que ela o
   pinta`. `_escala_tipografica` **gera as regras a partir desta tabela**, e quem reserva espaço
   para esse texto lê a mesma tabela. Um seletor novo entra uma vez e as duas pontas andam juntas.
2. **`ui/tipografia.altura_do_texto(pontos)`** — pura, e **por cima**: `ceil(pontos × 15/8)`,
   calibrada contra `QFontMetrics.height()` medido nesta árvore (`ALTURA_POR_PONTO`). Reservar de
   mais é ar; reservar de menos é letra apagada.
3. **`qt/tema.altura_do_titulo_atual()`** — quem tem toolkit mede a fonte **exata** que a folha
   pinta (`QFontMetrics(fonte_pintada("QGroupBox::title")).height()` = 21 px) e passa o número
   para a folha, como já fazia com `marcas`. A conta pura é a reserva de quem não tem tela.
   `tema.fonte_pintada(seletor)` levanta para seletor que a folha não pinta, pela disciplina de
   `tokens.cor`: um seletor escrito errado devolveria uma altura plausível e sem significado.

Medido, na janela viva: a faixa passou de **4 px** (compacta) e **6 px** (confortável) para
**21 px** nas duas; o título pinta de `y=0` a `y=21` e o primeiro filho começa em `y=30` na Estudo,
`y=33` na Galeria e `y=35` no Resultado.

### 1.2 O instrumento: a régua pergunta a fonte **à folha**

`src/caissa/ui/audit/texto_pintado.py` é o portão novo. Ele **não tem uma tabela de seletores**:
lê a folha aplicada (`QApplication.styleSheet()`), acha toda declaração de `font-*`, e resolve
qual fonte o Qt vai usar para desenhar cada subcontrole. Uma regra de fonte nova entra na régua no
mesmo commit em que entra na folha, e um seletor que a análise não entenda é **número publicado**
(`seletores de fonte que a regua NAO analisou: 0`) em vez de silêncio.

E ele lê **a caixa** pela mesma porta, que era a segunda metade do ponto cego:
`QHeaderView::section { padding: 2px 6px; border-right: 1px }` come **13 px** da largura da seção,
e perguntar isso ao estilo da plataforma (`PM_HeaderMargin`) devolve outro número.

```
Texto PINTADO: a regua le a fonte da folha de estilo, e nao QWidget.font().
  arranjo                 tamanho  medidos  cegos  cobertos  cortados  veredito
  classica/compacta    1280x800         31      1         0         0  PASSOU
  ... (24 linhas: 3 peles x 2 densidades x 4 larguras) ...
  fita/confortavel     3840x2160        21      1         0         0  PASSOU

  seletores de fonte que a regua NAO analisou: 0 []
  medidos 564 | cegos (folha != widget) 24 | cobertos 0 | cortados 0
  Veredito: PASSOU
```

**A coluna "cegos" é o tamanho do ponto cego, e ela é o número que faltava**: são os textos em que
a folha pinta uma fonte que `QWidget.font()` não tem. Quando esta régua rodou pela primeira vez
neste ciclo ela achou **84**; hoje ela acha **24**, e a diferença é o item 2 — os cabeçalhos de
coluna dos treze diálogos deixaram de divergir porque a varredura da escala passou a alcançá-los.
Os 24 que sobram são a aba selecionada de cada passada: `QTabBar::tab:selected { font-weight:
bold }` é a única regra da folha que muda o desenho sem que ninguém mude o objeto, e ela alarga
sem crescer.

### 1.3 A prova de que a cegueira fechou

`--faixa-de-antes` reaplica a folha com a reserva de antes do ciclo 14 (`espaco.linha()`, 4 px na
compacta e 6 px na confortável) **sem tocar um byte do produto**, e a régua volta a acusar:

```
  arranjo                 tamanho  medidos  cegos  cobertos  cortados  veredito
  classica/compacta    1920x1080        21     21         6         0  REPROVOU
  classica/confortavel 1920x1080        21     21         3         0  REPROVOU
  ... nas 24 combinações ...
  medidos 564 | cegos 564 | cobertos 108 | cortados 0
  Veredito: REPROVOU

    classica/compacta   1280  aba Resultado   Reconhecido (clique e arra  COBERTO 3px  (TabuleiroEditavel)
    classica/compacta   1280  aba Estudo      Lances                      COBERTO 8px  (QTextBrowser)
    classica/compacta   1280  aba Estudo      Comentário do lance         COBERTO 8px  (QTextEdit)
    classica/compacta   1280  aba Dataset     Filtros                     COBERTO 8px  (QLabel, QLineEdit)
    classica/compacta   1280  aba Galeria     Cabeçalhos do PGN           COBERTO 5px  (QLabel, QLineEdit)
    classica/compacta   1280  aba Galeria     Este diagrama               COBERTO 5px  (BarraFluida)
```

**Seis títulos, seis números, e eles são os do §3 da crítica à unidade** — 3 / 8 / 8 / 8 / 5 / 5 na
compacta, e 3 de 6 na confortável. A régua que devolvia `0` por três ciclos devolve o defeito.

E a aritmética do próprio crítico fecha, no instrumento dele
(`c13_titulo_de_grupo_cortado.py classica 1920`, com `CVOFF_DENSITY=compacta`):

```
  === pele classica, 1920 px: QGroupBox com titulo, visiveis: 6
      titulos cuja tinta pintada INVADE a borda do proprio quadro: 0
      onde        titulo                     faixa  pintado   9pt  invade
      Estudo      Lances                        21       21    21       0
      ... (os seis) ...
```

**`faixa = pintado = 21`.** A faixa era 4 e o pintado 21; hoje os dois números saem da mesma
escala, e é por isso que eles são iguais e não por coincidência.

### 1.4 As fotografias, e eu olhei

`benchmarks/reports/ui/c14/c14_recorte_do_titulo.py` grava o par decisivo — mesma pele, mesma
densidade, mesma largura, mesmo recorte de 300×44 px a partir da origem do grupo, **só a faixa
muda**:

* `c14_ANTES_fita_compacta_Estudo_Lances.png` — `Lances` sai baixo, encavalado no filete do quadro,
  com a metade de baixo das letras comida pela borda e pelo `QTextBrowser`.
* `c14_DEPOIS_fita_compacta_Estudo_Lances.png` — `Lances` inteiro, negrito, acima do quadro.
* o mesmo par para `Comentário do lance` (onde o `á` e o `ç` são o teste), `Filtros`,
  `Cabeçalhos do PGN`, `Este diagrama` e `Reconhecido (clique e arraste…)`.
* e a aba inteira: `c14_ANTES_fita_compacta_aba_Estudo.png` ao lado de
  `c14_DEPOIS_fita_compacta_aba_Estudo.png`, 1920×1080.

**Os seis arranjos** × ANTES/DEPOIS × (6 grupos + a aba Estudo inteira) = **84 PNG, 42 pares**. E, pela mesma disciplina, as
oito telas de diálogo que este ciclo mexeu foram fotografadas e olhadas
(`c14_dialogo_*.png`): o `Filtro` com maiúscula e o cabeçalho `Resultado` inteiro em
`DialogoDePartidas`; as duas caixas de `Achar e substituir` fechando na mesma coluna; o título e o
`Fechar` de `JanelaDeEstatisticas`; e a linha do `Ctrl+Shift+S` terminando em `(.cvtxt)` em vez de
`(.cvt`. **Olhei os pares um a um**,
ampliados, antes de escrever esta linha — e o que se vê no ANTES é o título encolhido contra o
filete do quadro, com as hastes de baixo do `ç` e do `g` sumindo dentro dele; no DEPOIS ele é um
rótulo de painel inteiro.

### 1.5 Todo lugar onde um token de espaçamento reservava para texto da folha

A ordem de serviço pediu a varredura. A folha tem **quatro** regras que trocam a fonte no desenho
(`§1.6` da crítica), e cada uma tem — ou não — alguém reservando espaço para ela:

| regra da folha | quem reservava | estava certo? | hoje |
|---|---|---|---|
| `QGroupBox::title` 12 pt negrito | `margin-top: espaco.linha()` | **NÃO** — 4 px para 21 px | `tipografia.altura_do_texto(escala[TITULO])`, medido = 21 px |
| `QHeaderView::section` 12 pt negrito | `qt/tabela._largura_da_secao` com `QFontMetrics(cabecalho.font())` | **nas abas sim, nos diálogos não** — lá o widget ficava em 9 pt | a varredura da escala passou a alcançar o diálogo (`escala_do_dialogo`) |
| `QTabBar::tab:selected` negrito | o Qt, com a fonte do `QTabBar` | mede a mais, não a menos: negrito só alarga, e a fila de abas tem `Scroll Right` | medido: **0 cortados** nas 24 combinações |
| `QLabel[apoio="true"]` 8 pt | ninguém precisa: 8 pt é **menor** que o corpo | sim | medido junto, 0 cortados |

O segundo é o item 2 do §7 do ciclo 13, e ele caiu junto com o bloqueante — é o que a crítica
previu (*"com ela, o item 2 abaixo cai junto"*).

---

## §2 — Os itens não bloqueantes, um a um, com o número

### Item 2 — `Resultado` elidido no cabeçalho de `DialogoDePartidas` · **fechado**

A causa é a mesma do bloqueante — duas fontes onde devia haver uma —, e a **raiz** é mais simples
do que parecia. `qt/tabela._largura_da_secao` mede com `QFontMetrics(cabecalho.font())`, e essa é
a pergunta certa: a fonte do widget **deveria** ser a que desenha. Nos treze diálogos ela não era,
e o motivo é de escopo, não de tipografia: **`qt/escala.aplicar_escala` roda uma vez, no fim da
montagem da janela, e os diálogos são montados depois.** `QHeaderView` está em
`ui/tipografia.PAPEL_POR_CLASSE` desde o ciclo 2 — nas seis abas o cabeçalho é 12 pt negrito e
sempre foi; nos diálogos ele ficava no corpo de 9 pt, e a folha o pintava a 12 pt negrito assim
mesmo. É a **quarta** cegueira por largura desta frente (regra, pele, janela, e agora *quando* a
varredura roda), e ela morreu do mesmo jeito que as outras três: a decisão saiu de uma chamada
para um evento.

**O conserto é uma linha no filtro que já existia.** `qt/acessibilidade._VigiaDeDialogos`, que
nomeia e traduz todo `QDialog` no `QEvent.Show` desde o ciclo 12, passa a aplicar a escala também
(`escala_do_dialogo`). Não foi ensinar mais um consumidor a perguntar à folha: foi fazer as duas
fontes voltarem a ser uma. O efeito é medido pela régua nova: os textos "cegos" caem de **84 para
24**.

```
                    ANTES                       DEPOIS
  Resultado   tinta 76 px   espaço 67 px   ->   tinta 76 px   espaço 87 px    (CORTADO 9 -> 0)
  Lance       tinta 44 px   espaço 42 px   ->   tinta 44 px   espaço 55 px    (CORTADO 2 -> 0)
```

**E foi um teste do tronco que apontou a raiz.** A primeira forma deste conserto ensinava
`_largura_da_secao` a perguntar a fonte à folha; ela passava isolada e derrubava
`tests/test_qt_tabela.py` em três lugares na suíte inteira, porque lá a tabela é montada sem folha
e a asserção é de **igualdade** com `cabecalho.font()`. O teste estava certo e o conserto estava
no lugar errado: a função tem de medir a fonte do widget, e o defeito era o widget estar com a
fonte errada. Trocado o conserto pela raiz, os três voltam a passar sem uma linha de teste
alterada.

*Alvo: 0 de 24 cabeçalhos elididos. Hoje: **0 de 24 nas três peles**, medido pelo instrumento do
**crítico** (`c13_fonte_pintada.py <pele> 1366`), que devolvia `ELIDIDOS pela fonte que a tela
pinta: 2`; e `cortados 0` nas 24 combinações do portão novo.*

### Item 3 — `Ok → "Confirmar"` em 32 caixas de alerta · **revertido, e a regra virou teste**

Foi regressão minha do ciclo 12, e o argumento escrito era o errado: `LETRAS_MINIMAS` nasceu no
ciclo 1 para reprovar `-`, `+` e `◀` — **glifos que não anunciam nada** — e foi aplicada a texto
**desenhado**, escrevendo `Confirmar` no botão único de 32 caixas de aviso, inclusive a de *Sobre o
produto*.

**Duas coisas mudaram, e a segunda é a que impede a repetição:**

1. `BOTOES_PADRAO["Ok"] = "OK"` — a palavra do `qtbase_pt_BR.qm` que esta árvore já traz.
2. **A regra passou a ser: onde o Qt tem palavra, a palavra é do Qt.** `ui/strings` registra o
   catálogo medido (`TRADUZIDOS_PELO_QT`, 18 de 18) e as exceções com o motivo escrito
   (`DIVERGENCIAS_DECLARADAS`); `tests/unit/ui/test_botoes_padrao.py` cobra que nenhuma
   divergência fique sem motivo, e sem abrir Qt.

Medido por `benchmarks/reports/ui/c14/c14_catalogo_do_qt.py`, contra o `.qm` de verdade:

```
  catalogo: PyQt6/Qt6/translations/qtbase_pt_BR.qm   carregou=True
  concordam com o Qt: 16   divergem (todas declaradas?): 1   o Qt nao traduz: 1
  divergencias NAO declaradas: 0 []
  registradas que o Qt de hoje escreve diferente: 0 []
```

Cinco palavras voltaram para as do Qt: `Ok → OK`, `YesToAll → Sim para tudo`,
`NoToAll → Não para tudo`, `RestoreDefaults → Restaurar padrões`, `Retry → Repetir`. **A única
divergência que fica é `Abort`**, e o motivo está escrito: o catálogo do Qt escreve `Cancelar`,
que é a **mesma** palavra que ele dá ao `Cancel`, e a única caixa de três botões do produto
(`qt/exportador.py:104`) desenha os dois lado a lado.

E a régua ganhou a exceção escrita: `teclado.PALAVRAS_CURTAS_LEGITIMAS = {"ok"}`, com o teste que
prova que ela **não** afrouxou — `-`, `+`, `|◀`, `<`, `>`, `121` e `...` continuam reprovados.

*Ressalva declarada:* o instrumento do crítico `c13_caixas_de_mensagem.py` tem uma lista de
palavras inglesas que inclui `OK`, então ele agora conta **5 de 14 botões "em inglês"**. São os
cinco `OK`, e `OK` é a palavra pt-BR — é o alvo do próprio item 3 do §7. O número que responde a
pergunta é o do parágrafo acima.

### Item 4 — nenhum dos treze diálogos usava `qt/vazio.EstadoVazio` · **0 de 5 → 5 de 5**

```
  estados vazios (qt/vazio.EstadoVazio) montados na janela principal: 4

  tela                                      vistas  vazias  EstadoVazio  situacao
  DialogoDePartidas (Galeria | Partidas)         2       2            1  usa o componente  Nenhuma partida guardada
  JanelaDeBusca (Achar no texto)                 1       1            1  usa o componente  Digite o que procurar
  JanelaDeBusca (substituindo)                   1       1            1  usa o componente  Digite o que procurar
  _JanelaDeColecao (Estudo | Abrir PGN)          1       1            1  usa o componente  Nenhuma partida neste arquivo
  _JanelaDePartidas (Estudo | Partidas)          1       1            1  usa o componente  Nenhuma partida chega aqui

  telas de dialogo com uma vista VAZIA na tela: 5   dessas, com o componente: 5
```

Seis pares título+frase novos em `ui/strings.py`, cada um com as três partes do contrato: **o título diz o
que falta, a frase diz por que está vazio e o que enche, e o botão faz.** Dois vazios distinguem
a causa, porque a saída é diferente:

* `DialogoDePartidas` — *"Nenhuma partida guardada"* + `Procurar por nome` quando a lista está
  vazia; *"Nenhuma partida com esse filtro"* **sem botão** quando é o filtro que não casou.
* `JanelaDeBusca` — *"Digite o que procurar"* antes da primeira letra; *"Nada achado"* depois.

E `_JanelaDePartidas` **parou de dizer a mesma coisa duas vezes**: a frase de `resposta` que ficava
num rótulo acima da lista some enquanto o vazio está na tela, porque o vazio já a diz — dentro do
vazio, e com o botão junto. É a duplicação que o §7 do ciclo 2 mandou apagar na Galeria, onde eram
duas frases iguais a 320 px uma da outra.

E `_JanelaDeColecao` **parou de se contradizer**: ela escrevia `"0 partida(s) em colecao.pgn.
Escolha uma:"` sobre uma lista vazia — a segunda oração pedindo o que a primeira acabou de dizer
que não existe. Sem partida, quem fala é o estado vazio.

### Item 5 — `JanelaDeAtalhos` abria 12 px mais estreita que o conteúdo · **fechado**

```
                       janela      viewport   conteudo   rola H   rola V
  ANTES (ciclo 13)     499x519       459 px      471 px    12 px   220 px
  DEPOIS               513x519       473 px      471 px     0 px   208 px
```

`QScrollArea` **não** pede largura pelo widget que ela embrulha — o `sizeHint` dela é o do próprio
quadro. A janela passa a declarar `setMinimumWidth(grade + moldura×2 + barra vertical)` e a chamar
`adjustSize()` no fim da montagem. *Alvo: 0 px de rolagem horizontal. Hoje: **0**.*

### Item 6 — os três buracos do achador sintático · **os três fechados, e o portão parou de afirmar largura que não tem**

O crítico abriu três buracos com sabotagens próprias. Rodei o instrumento **dele**,
`c13_sabotar_o_achador.py`, sem alterar uma linha:

```
  sha256 de qt/*.py ANTES : addecb88fd41d2585a438de4d87e75ea09ba6ef176313e03a5819c51083e80d4

  (b_heranca_direta)  13o QDialog por heranca direta      ve? True   o portao LEVANTOU -> _JanelaDeSondaC13
  (d_apelido)         `Base = QDialog` + `class X(Base)`  ve? True   o portao LEVANTOU -> _JanelaDeApelidoC13
  (e_qmessagebox)     `class X(QMessageBox)`              ve? True   o portao LEVANTOU -> _CaixaDeSondaC13
  (f)                 QDialog em qt/<subpasta>/novo.py    ve? True   o portao LEVANTOU -> _JanelaEmSubpastaC13

  sha256 de qt/*.py DEPOIS: addecb88fd41d2585a438de4d87e75ea09ba6ef176313e03a5819c51083e80d4
  a pasta do tronco voltou identica: True     sobra alguma sonda? []
```

**Quatro de quatro levantam nomeando**, e `qt/*.py` volta byte a byte. Os consertos:

* `_apelidos()` segue a atribuição simples de nome para nome, com teto para não haver laço;
* `qt.BASES_DE_DIALOGO_DO_QT` lista as **nove** classes do Qt que *são* diálogos (`QMessageBox`,
  `QFileDialog`, `QWizard`…), e não só a base direta;
* `rglob("*.py")` no lugar de `glob("*.py")`.

**E a frase publicada encolheu para o tamanho da medição.** Ela dizia *"os 12 `QDialog` que o
produto declara"*; agora diz:

```
  --- os 12 QDialog que o produto declara COMO CLASSE, em 13 telas ---
      fora da varredura sintatica: QDialog construido em linha (painel_de_estudo.ampliar_recorte,
      S-282) e toda QMessageBox; quem os prepara e' o filtro de QEvent.Show de qt/acessibilidade.
```

O quarto buraco **é do produto e não tem conserto sintático**: um `QDialog(self)` construído dentro
de um método não tem classe para a árvore ler. Ele está limpo porque o remédio mora no
`QEvent.Show` — é a razão de a decisão ter sido posta lá no ciclo 12, e agora está dito em voz alta
em vez de virar a quarta cegueira por largura.

### Item 7 — a barra do `DialogoDeTreino` · **determinada**

```
  [DialogoDeTreino] barra antes de iniciar:  0..0   (indeterminada)   formato '%p%'
  [DialogoDeTreino] apos progresso(3, 8):    0..8   valor=3           formato 'época %v de %m'
  [DialogoDeTreino] diz onde se cancela: ['Fechar esta janela não interrompe o treino:
                                          quem cancela é o rodapé.']
```

`ControladorDeTreino` ganhou o sinal `avancou(int, int)` — sinal e não chamada direta pela mesma
razão de `escreveu`: quem conta épocas é a thread do treino. `iniciar()` emite `(0, pedido.epochs)`
**antes da primeira época**, porque o total já é conhecido ali; `_progresso` emite `(k, n)` a cada
época, o mesmo par que já ia para o rodapé. O texto da barra é o mesmo do rótulo e o do rodapé —
*época k de n* —, porque três lugares dizendo a mesma coisa com três palavras diferentes é o que
faz procurar a diferença que não existe.

### Item 8 — a lista de E/S de disco declarada · **saiu do relatório e entrou no portão**

O item 13 do ciclo 11 pediu que a lista cobrisse o que o perfil nomeia; o ciclo 12 respondeu com
**quatro caminhos escritos à mão no relatório**, e o crítico do ciclo 13 mediu **seis**. Uma lista
escrita à mão sobre uma medição que o programa já tem é a forma de errar que este arnês existe para
não ter.

Duas mudanças em `caissa.ui.audit.bloqueio`:

* `PISTAS_DE_DISCO` ganhou `sqlite3` — e a falta dele **era a causa** de a lista dizer quatro:
  `_sqlite3.connect` e `Connection.__exit__` caíam no balde `builtins (C)`. Um `connect` abre um
  arquivo, um `execute` o lê e um `__exit__` é o `COMMIT` que o escreve. (Isto move tempo entre
  famílias publicadas, e o preço está declarado no docstring.)
* `atribuir()` devolve `e_s_de_disco` — todo quadro classificado como disco, **com quem desta
  frente o disparou**, e a tabela do terminal o imprime.

O portão nomeia hoje, na pior execução das três:

```
  E/S de disco na thread da janela que o perfil nomeia (acima de 0,05 ms):
     37.50 ms  <built-in method nt.stat>                     <- marcas.py:77 _marca_de
     22.30 ms  <method '__exit__' of 'sqlite3.Connection'>   <- painel_da_galeria.py:1106 _abrir_cache_de_posicoes
     10.29 ms  <method 'execute' of 'sqlite3.Connection'>    <- janela.py:1763 _atualizar_abas
      2.22 ms  pathlib.py:438 _select_from                   <- escolha_de_bases.py:48 _mesmo_conjunto
      1.75 ms  <built-in method _sqlite3.connect>            <- painel_da_galeria.py:1106 _abrir_cache_de_posicoes
      0.91 ms  <built-in method nt.scandir>                  <- escolha_de_bases.py:48 _mesmo_conjunto
      0.91 ms  <built-in method nt._getfinalpathname>        <- state.py:270 _history_key
      0.42 ms  <built-in method nt.mkdir>                    <- painel_da_galeria.py:1106 _abrir_cache_de_posicoes
      0.40 ms  <method 'commit' of 'sqlite3.Connection'>     <- painel_da_galeria.py:1106 _abrir_cache_de_posicoes
      0.26 ms  <built-in method io.open>                     <- campo.py:168 _ler
      (mais 4 quadros de `pathlib` entre 0,07 e 0,17 ms, que são análise de caminho e não disco)
```

*Alvo: a lista cobre o que o perfil nomeia. Hoje: **14 quadros nomeados, 10 deles toques de disco
de verdade, e os 6 do crítico estão entre eles** — e a lista não é mais minha, é do portão.* Ele
achou quatro caminhos que ninguém tinha nomeado: `nt._getfinalpathname` em `state._history_key`,
`nt.mkdir` e `Connection.commit` em `_abrir_cache_de_posicoes`, e `io.open` em `campo._ler`.

### Item 9 — os dois campos de `JanelaDeBusca` · **uma borda esquerda e uma direita**

```
                    esquerda        direita
  ANTES (ciclo 13)  57 e 78 px      505 e 396 px
  DEPOIS            [74]            [394]
```

A esquerda vem dos dois rótulos com a **mesma** largura; a direita, de uma calha do tamanho do
botão reservada na linha de cima — e ela **some junto com a linha que ela alinha**, porque alinhar
com uma linha escondida seria um buraco de 100 px à direita do campo `Achar`. A calha é
sincronizada no `showEvent`, e não só na montagem: a escala tipográfica chega no `QEvent.Show` e
põe o degrau `ACAO` (peso 600) no botão, que fica **1 px** mais largo. Um pixel é pouco e é
exatamente a diferença que este item existe para não ter.

### Item 10 — `filtro` vira `Filtro` · **fechado**

Era o único rótulo de campo dos treze diálogos que não começava com maiúscula
(`DialogoDePartidas`). Medido: **0 rótulos de campo em minúscula**; o instrumento casa rótulo com
campo pela geometria (mesma linha, à esquerda) e acha 4 pares nos treze diálogos, todos com
capitalização de frase.

### Item 11 — `JanelaDeEstatisticas` deixou de ser um despejo · **fechado**

```
  [JanelaDeEstatisticas] botoes desenhados: 1 ['Fechar']   titulo na tela: ['Estatísticas do dataset']
```

Era a única das treze telas **sem botão nenhum**. Ganhou o título desenhado (no degrau `TITULO` da
escala, pela propriedade `papel_de_fonte`) e o `Fechar` que faltava. O corpo continua monoespaçado
de propósito — é uma tabela alinhada por espaço, e em proporcional ela deixa de ser tabela.

### Item 12 — os que continuam abertos, com os números de sempre

Declarados, sem atenuação, e nenhum precisa fechar para aprovar:

* **bloqueio > 16 ms** — **REPROVOU**: 7 operações, pior **221,6 ms**, mediana **142,9 ms**
  (`abrir PDF`), com a passada rodando **sozinha na máquina**. Parte desta frente no perfil:
  **1,6 % a 3,1 %**. Mesma ordem de grandeza dos ciclos 12 e 13 (223,5 / 149,1 e 240,7 / 152,1).
* **`Motivo` ilegível** na Revisão; **0 de 5** cabeçalhos de fita desenhados na compacta (4 de 4
  filetes; 5 de 5 no pleno a 1920); **6 de 24** botões de fita sem rótulo desenhado.
* **tinta dos ícones** e a caixa de **2×17 px** na fita confortável — o censo devolve
  **0 glifos de texto em todos os seis arranjos**, e a amplitude relativa continua acima do alvo.
* **vazio de painel a 4K**, remedido sobre as 72 capturas **deste** ciclo: 5 de 6 painéis
  acima de 200 kpx — Revisão **3 104,2**, Texto **2 050,6**, Dataset **1 896,8**, Estudo
  **1 540,8**, Galeria **1 535,0**, Resultado **43,3** kpx. Os três que têm grupo encolheram
  um pouco (1 905,3 → 1 896,8; 1 569,6 → 1 540,8; 1 550,0 → 1 535,0): é a faixa do título
  ocupando espaço que era vazio. O item de desenho continua aberto.
* **6 de 18** últimas linhas curtas (< 20 % da medida), que é o preço declarado de `sem_orfa`.
* **marca da FEN só à direita**; a etiqueta local que segura `7bcb396`.

---

## §3 — Os portões, todos rodados

| portão | resultado |
|---|---|
| **Texto pintado (novo)** | 3 peles × 2 densidades × 4 larguras = **24 passadas**, 564 textos, **24 cegos** (eram 84 antes do item 2), **0 cobertos, 0 cortados, 0 seletores fora da análise**. **PASSOU** |
| **Texto pintado, prova de vida** | com a faixa de antes: **108 cobertos** nas 24 passadas — 6 de 6 na compacta, 3 de 6 na confortável. **REPROVOU**, que é o que ela tem de fazer |
| **Teclado + nome + papel** | **216/216/240/240/360/360** nas abas, **50 focáveis em 13 telas de diálogo** por arranjo, **0 sem nome, 0 sem papel, 0 nome vazio, 0 fora do Tab** nos seis. **PASSOU** |
| **Prova de vida do achador de diálogos** | **4 de 4** sabotagens levantam nomeando; `qt/*.py` `sha256` idêntico antes e depois |
| Contraste WCAG AA | **300 pares / 220 sob portão / 0 reprovados** nas duas polaridades × duas densidades; menor folga **3,27:1** e **3,03:1**. **PASSOU** |
| **Bloqueio > 16 ms** | **REPROVOU**: 7 operações, pior 221,6 ms, mediana 142,9 ms; e agora ele **nomeia 14 quadros de E/S de disco** (10 deles toques de disco de verdade) com quem os disparou |
| Fita (geometria) | `topos [0,49] alturas [43]` na compacta, `[0,51]/[45]` na confortável, `[0]/[81]` no pleno a 1920; **5 de 5** cabeçalhos no pleno, 4 de 4 filetes no compacto — **idêntico ao ciclo 13** |
| Censo de ícones | **0 glifos de texto em todos os seis arranjos** |
| Diálogos (instrumento do ciclo 11, do crítico) | `DEFEITOS nos 6 dialogos: antes=0 depois=0` |
| Estados vazios dos diálogos (novo) | **5 de 5** telas que abrem vazias usam `EstadoVazio` (era 0 de 5), **nas três peles** |
| Catálogo do Qt (novo) | 16 concordam, 1 divergência declarada, 0 não declaradas |
| Vazio de painel a 4K | 5 de 6 acima de 200 kpx, pior 3 104,2 kpx |
| Texto cortado nos diálogos (régua do ciclo 11, do crítico) | `textos que NAO CABEM nos 13 dialogos: 0` |
| Cabeçalho com a fonte pintada (`c13_fonte_pintada`, do crítico) | **0 elididos de 24**, nas três peles a 1366 px — eram **2** |
| Aritmética da faixa (`c13_titulo_de_grupo_cortado`, do crítico) | `faixa=21 pintado=21 invade=0` nos seis grupos — a faixa era 4 |

---

## §4 — Suítes

| suíte | resultado |
|---|---|
| `tests/unit/ui` (nossa, F9) | **238 passed** em 2,6 s — eram **198**; entraram **40** |
| **nossa, sem `tests/integration/test_packaging.py`** | **3 126 passed, 1 skipped, 0 failed** em 733,3 s — eram **3 086, 1, 0**; entraram os **40**. O pulo é o de sempre (`test_fonts.py`, WOFF2 sem Brotli) |
| **tronco inteiro** | **3 failed, 4 486 passed, 2 skipped, 4 536 subtests** em 293,7 s — **os mesmos números do ciclo 13**, e as três reprovações são as pré-existentes: `test_docs::test_a_arvore_do_README_lista_todo_modulo_do_pacote`, `test_editor_model::SemTkinterTests::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter` e `test_strings::AccentTests::test_no_ui_string_uses_an_unaccented_portuguese_word`. Nenhuma é desta frente |

---

## §5 — Nota de procedimento

* **Conferi o caminho de saída de todo script antes de rodá-lo.** Os instrumentos que reusei —
  `c11_dialogos_prova.py`, `c12_fita.py`, `c12_icones_da_janela.py`, `c5_vazios.py`,
  `c13_titulo_de_grupo_coberto.py`, `c13_cabecalho_elidido.py`, `c13_fonte_pintada.py`,
  `c13_caixas_de_mensagem.py` — **não gravam nada**, conferido por busca de
  `write_text`/`json.dump`/`.save(`/`mkdir` antes de cada um. `c13_sabotar_o_achador.py` escreve e
  apaga arquivos novos em `qt/` e devolve a pasta com o mesmo `sha256`.
* **`QT_QPA_FONTDIR=C:\Windows\Fonts` em toda invocação**, com barra simples — é a armadilha que
  `capture.PASTA_DE_FONTES` documenta e que pegou o crítico na primeira passada dele.
  `PYTHONDONTWRITEBYTECODE=1` em tudo. `--saida` explícito em todo portão.
* **Nada foi escrito fora de** `src/caissa/ui/`, `tests/unit/ui/`, `benchmarks/reports/ui/c14/`,
  `docs/quality/F9_REPORT_C14.md` e do frontend do tronco (`chess_diagram_ocr/ui/` e `/qt/`).
* **Nenhum teste foi afrouxado.** A única régua que mudou de alcance foi `LETRAS_MINIMAS`, e a
  exceção é uma palavra nomeada com o motivo escrito, com o teste que prova que os glifos
  continuam reprovados. Nenhum arquivo cresceu para bater catraca: `qt/janela.py` continua em
  1 883 linhas e `test_packaging.TamanhoDaJanelaTests.LIMITE` continua 1 883.
* **Nenhuma linha de teste do tronco foi alterada** — e três delas mudaram o conserto de lugar.
  A primeira forma do item 2 punha `_largura_da_secao` a perguntar a fonte à folha, e
  `tests/test_qt_tabela.py` caía em três pontos na suíte inteira (passava isolada, porque lá a
  folha ainda não tinha sido aplicada por um teste anterior no mesmo processo). O teste estava
  certo; o conserto é que estava no consumidor em vez de estar na raiz. Ver o item 2.
* **`tests/unit/ui/test_arquitetura.py` deixou de ter uma lista escrita à mão.** A parametrização
  de "todo arnês de auditoria importa sem Qt" tinha sete nomes cravados, e `texto_pintado` teria
  nascido fora dela; agora ela lê a pasta. É o mesmo defeito que reprovou os ciclos 9, 11 e 13,
  um andar abaixo, e ele estava dentro do meu próprio teste.


---

## §6 — Como reproduzir

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=<suite>\src;<tronco>\src
set PY=..\ChessVisionOFF_Puro\.venv\Scripts\python.exe
set C14=benchmarks\reports\ui\c14

:: O BLOQUEANTE, pelas duas metades
%PY% -m caissa.ui.audit.texto_pintado --pdf "...\1937 Kemeri.pdf" --saida %C14%\gates
     :: 24 passadas, 564 textos, 24 cegos, 0 cobertos, 0 cortados. PASSOU
%PY% -m caissa.ui.audit.texto_pintado --pdf "..." --faixa-de-antes --saida %C14%\prova_de_vida
     :: a MESMA regua com a reserva de antes: 108 cobertos, 6 de 6 na compacta. REPROVOU

:: os instrumentos do critico, sem alterar uma linha
%PY% benchmarks\reports\critique\ui\c13\c13_titulo_de_grupo_coberto.py <pele> <densidade> 1920
     :: 0 de 6 nos seis arranjos (era 6 de 6 na compacta, pior 8 px de 21)
%PY% benchmarks\reports\critique\ui\c13\c13_fonte_pintada.py classica 1366
     :: 0 elididos (eram 2: `Resultado` 76 px numa secao de 68, e `Lance`)
%PY% benchmarks\reports\critique\ui\c13\c13_sabotar_o_achador.py
     :: (b)(d)(e)(f): as QUATRO levantam nomeando; qt/*.py identico antes e depois
%PY% benchmarks\reports\critique\ui\c11\c11_dialogos_prova.py     :: antes=0  depois=0

:: as fotografias -- o par decisivo, mesma pele, mesma largura, so a faixa muda
%PY% %C14%\c14_recorte_do_titulo.py fita compacta --antes
%PY% %C14%\c14_recorte_do_titulo.py fita compacta
     :: c14_ANTES_fita_compacta_Estudo_Lances.png  ao lado de  c14_DEPOIS_...

:: os itens nao bloqueantes, cada um com o seu numero
%PY% %C14%\c14_catalogo_do_qt.py          :: 16 concordam / 1 divergencia declarada / 0 nao declaradas
%PY% %C14%\c14_vazios_dos_dialogos.py     :: 5 de 5 telas vazias usam EstadoVazio (era 0 de 5)
%PY% %C14%\c14_miudezas_dos_dialogos.py   :: atalhos 0 px H; busca [74]/[395]; estatisticas 1 botao;
                                          :: treino 0..8 "epoca %v de %m"; 0 rotulos em minuscula

:: os portoes de sempre
%PY% -m caissa.ui.audit.teclado   --pdf "..." --saida %C14%\gate_teclado   :: PASSOU nos seis
%PY% -m caissa.ui.audit.contraste --saida %C14%\gates                      :: 300/220/0. PASSOU
%PY% -m caissa.ui.audit.bloqueio  --pdf "..." --saida %C14%\gates          :: REPROVOU; 11 E/S de disco
%PY% benchmarks\reports\ui\c12\c12_fita.py
%PY% benchmarks\reports\ui\c12\c12_icones_da_janela.py
%PY% -m caissa.ui.audit.capture --saida %C14%\capturas --marca c14 --pdf "..."   :: as 72
%PY% benchmarks\reports\critique\ui\c5\c5_vazios.py %C14%\capturas\c14_claro_3840*.png

:: as suites
.venv\Scripts\python.exe -m pytest tests\unit\ui -q
.venv\Scripts\python.exe -m pytest tests -q --ignore=tests\integration\test_packaging.py
<tronco>\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly
```

Artefatos meus, todos em `benchmarks/reports/ui/c14/`: os quatro instrumentos, `capturas/`
(72 capturas do arnês, 84 recortes ANTES/DEPOIS e 8 retratos de diálogo), `gates/` (texto
pintado, contraste, bloqueio), `gate_teclado/` e `prova_de_vida/`. **Nada fora desta pasta, de `src/caissa/ui/`, de
`tests/unit/ui/`, de `docs/quality/F9_REPORT_C14.md` e do frontend do tronco.**
