# F9 — Interface, crítica do ciclo 13

```
VEREDITO: REPROVADO
CICLO: 13
FRENTE: F9 (Interface)
```

**O bloqueante do ciclo 11 morreu, e morreu melhor do que a ordem de serviço pediu.** Rodei o
**meu próprio instrumento**, `c11_dialogos_prova.py`, sem alterar uma linha:

```
  DEFEITOS nos 6 dialogos:  antes=0   depois de nomear_tudo=0        (era antes=11)
      derivado: QLineEdit -> 'Achar'        QLineEdit -> 'Trocar por'
      derivado: QLineEdit -> 'Comando a procurar'   QScrollArea -> 'Atalhos de teclado'
```

O portão devolve, nos **seis** arranjos, `216 / 216 / 240 / 240 / 360 / 360` focáveis nas abas
**mais 46 focáveis em 13 telas de diálogo por arranjo**, com `0 sem nome, 0 sem papel, 0 nome
vazio, 0 fora do Tab` — batendo à unidade com o que eu remediei no ciclo 11. Rodei a mutação que a
ordem de serviço mandou eu rodar **eu mesmo** — um 13º `QDialog` entrando no produto — e o portão
**levanta nomeando‑o**, com o `sha256` de `qt/*.py` idêntico antes e depois. E o remédio é melhor
do que a lista: ele alcança **oito formas de `QMessageBox`** e um `QDialog` construído em linha
que a lista do portão **não consegue enxergar** — porque a decisão foi posta no `QEvent.Show` e
não numa tabela.

**Reprova por uma coisa, e ela é o décimo primeiro instrumento cego.** Os dez anteriores erraram a
**regra** (ciclos 1–8), a **pele** (ciclo 9: uma de três), a **janela** (ciclo 11: uma de treze) e
o **arquivo da certidão** (ciclo 12). Este erra a **fonte**: toda régua desta frente pergunta a
largura e a altura do texto a `QWidget.fontMetrics()`, e a tela pinta a fonte da folha de estilo —
`QGroupBox::title { font-size: 12pt; font-weight: bold }`, 21 px, dentro de uma faixa de
`margin-top: 4px`. O resultado está fotografado desde o ciclo 10 e ninguém olhou:

```
  classica / compacta / 1920 px      titulos de grupo visiveis: 6
      titulos com a tinta COBERTA pelo primeiro filho: 6 de 6      pior: 8 px de 21
      [Estudo]  Lances                margem= 9px  titulo=21px  COBERTO 8px por QTextBrowser
      [Estudo]  Comentário do lance   margem= 9px  titulo=21px  COBERTO 8px por QTextEdit
      [Dataset] Filtros               margem= 9px  titulo=21px  COBERTO 8px por QLabel, QLineEdit
```

`Lances`, `Comentário do lance` e `Filtros` chegam à tela com a **metade de baixo de cada letra
apagada** pelo widget de dentro do próprio grupo. Está em `z13_par_classica_compacta_COMPOSTO.png`
ao lado de `z13_par_classica_confortavel_COMPOSTO.png` — mesma pele, mesma largura, mesmo recorte,
só a densidade muda —, e está na captura **do construtor**,
`benchmarks/reports/ui/c12/capturas/c12_fita_1920x1080_estudo.png`, e na do ciclo 10,
`c10_fita_1920x1080_estudo.png`.

---

## Nota de procedimento

Rodei tudo do zero e conferi o destino de cada script antes de rodá‑lo.

* **Um erro meu, registrado porque ele quase virou uma acusação falsa.** Na primeira passada
  exportei `QT_QPA_FONTDIR` com a barra dobrada (`C:\\Windows\\Fonts`) dentro de um *heredoc*
  citado. O Qt subiu **sem fonte nenhuma**, todo glifo virou caixa, e o portão de teclado devolveu
  **222 / 246 / 366** em vez de 216 / 240 / 360 — seis focáveis a mais, um por aba, que eram os
  `QToolButton: Scroll Right` que o `QTabBar` cria quando a faixa de abas transborda. Com o texto
  medindo tofu, a faixa transborda. Corrigida a variável, o portão devolve **216 / 240 / 360, à
  unidade**. É exatamente a armadilha que `capture.PASTA_DE_FONTES` documenta por escrito, e ela
  me pegou. **O número do construtor reproduz; o meu primeiro é que estava errado.**
* **`data/janela.json` do tronco**: `sha256 a8e53bd5…a1` **antes** e `a8e53bd5…a1` **depois** das
  três execuções do portão de bloqueio — byte a byte. Copiei‑o para `c13/BACKUP_janela_c13.json`
  antes de qualquer coisa. `data/app_tkinter_state.json` continua com `mtime` **13:25**. O item 5
  do ciclo 11 está fechado, e eu o conferi com o hash e não com a palavra.
* **A minha sabotagem escreve um arquivo novo em `qt/` e o apaga**, e não edita nenhum arquivo
  existente. `sha256` da pasta inteira: `804238d0a838e35a41b667b82048b79b7214959c317c156b58a6f637bd603179`
  antes e depois — **o mesmo hash que o relatório do ciclo 12 publica**. `qt/` volta com 38 `.py`
  e zero sondas.
* Os instrumentos que reusei (`c11_dialogos_prova.py`, `c12_fita.py`, `c12_icones_da_janela.py`,
  `c5_vazios.py`) não gravam nada — conferido por busca de `write_text`/`json.dump`/`.save(`/
  `mkdir` antes de cada um.
* `PYTHONDONTWRITEBYTECODE=1` em toda invocação. `--saida` explícito em todo portão (e agora ele é
  **obrigatório**, que é o item 16 do ciclo 11 fechado).
* **Nada foi escrito fora de `docs/quality/F9_CRITIQUE_C13.md` e de
  `benchmarks/reports/critique/ui/c13/`.**

Instrumentos meus, todos em `benchmarks/reports/critique/ui/c13/`:

| instrumento | o que responde |
|---|---|
| `c13_sabotar_o_achador.py` | a mutação (b) do construtor **rodada por mim**, mais 3 sabotagens do achador sintático |
| `c13_caixas_de_mensagem.py` | as janelas que `dialogos_do_produto()` **não acha**: 8 formas de `QMessageBox` + o `QDialog` em linha |
| `c13_retrato_dos_dialogos.py` | os treze diálogos fotografados nas **três** peles (o ciclo 12 fotografou uma) |
| `c13_texto_cortado_nos_dialogos.py` | a régua de texto cortado do ciclo 11 apontada para os treze diálogos |
| `c13_fonte_pintada.py` | a mesma conta **com a fonte que a folha pinta** — cabeçalhos de coluna |
| `c13_titulos_pintados.py` | idem, títulos de grupo e aba selecionada |
| `c13_cabecalho_elidido.py` | o número exato do `Resultad·` de `DialogoDePartidas` |
| `c13_titulo_de_grupo_coberto.py` | **o bloqueante**: o título coberto pelo primeiro filho, nos 6 arranjos |
| `c13_titulo_de_grupo_cortado.py` | a aritmética da faixa (`margin-top`) contra a altura pintada |
| `c13_recorte_do_grupo.py` / `c13_par_de_densidades.py` | os recortes `z13_composto_*` e o par das duas densidades |

**Uma vez o meu olho errou e a medição corrigiu, e registro.** Achei que a tinta dos ícones
publicada no relatório (17,6 %–41,4 %, amplitude 80,8 %) não reproduzia; ela reproduz — eu tinha
lido só o último dos seis arranjos que o instrumento imprime. Em `classica/confortavel` e
`foco/confortavel`, grade de 16 px: **17,6 % a 41,4 %, amplitude relativa 80,8 %**, exatamente
como publicado. A régua é a favor do construtor e eu digo isso.

---

## §1 — Comparação às cegas (substituição do §2.1)

Mantida a substituição das rodadas anteriores: os **nove critérios de desenho**, cada um com a
pergunta *"isto sobrevive ao lado do Affinity Publisher, do Chessbase 17 e do Scrivener?"*.

### 1. Hierarquia visual — **NÃO SOBREVIVE na densidade Compacta**

Na `confortavel` a hierarquia é limpa: título de grupo em 12 pt negrito, corpo em 9 pt, apoio em
8 pt, e o degrau se lê. Na **Compacta** o degrau mais alto da escala é o que quebra: **6 de 6
títulos de grupo** têm de 3 a 8 px dos seus 21 px pintados **debaixo do primeiro filho**. Um
Affinity não tem um rótulo de painel com metade das letras apagada; este tem três (`Lances`,
`Comentário do lance`, `Filtros`), nas quatro abas mais usadas, nas três peles. É o §3 desta
crítica.

### 2. Ritmo espacial — **SOBREVIVE, e a regressão do ciclo 11 fechou**

Remedido com o instrumento do próprio construtor, nos seis arranjos:

```
  fita/compacta     1280·1366·1920   topos=[0, 49]   alturas=[43]
  fita/confortavel  1280·1366        topos=[0, 51]   alturas=[45]
  fita/confortavel  1920 (pleno)     topos=[0]       alturas=[81]
```

Os `topos [0, 6, 49, 55]` e as `alturas [31, 43]` do ciclo 11 sumiram: **uma fila, um topo, uma
altura**, que era o alvo com as minhas palavras. Os seis botões 12 px mais curtos e 6 px
encravados não estão mais lá.

### 3. Alinhamento — **SOBREVIVE no glifo; não sobrevive no cabeçalho de coluna**

`GLIFOS DE TEXTO em TODOS os arranjos: 0`, nos seis. A caixa do ícone fecha em 0×0 px em quase
toda grade, com as duas amplitudes abertas e declaradas (0×3 px na pílula da Foco, 2×17 px na fita
confortável). Mas o cabeçalho de `DialogoDePartidas` desenha **`Resultad·`**: pinta 76 px numa
seção de 68 px, nas três peles, com 160 px de folga nas colunas vizinhas. Não bloqueia — o produto
já carrega uma elisão maior e declarada (`Motivo`, 24 de 27 linhas a 1366) —, mas entra na lista.

### 4. Densidade × vazio — **NÃO SOBREVIVE, e o 4K continua onde estava**

Remedido com `c5_vazios.py` do ciclo 5, sem alteração, sobre as capturas do ciclo 12:

| painel | 3840 claro |
|---|---|
| Revisão | **3 104,2 kpx** |
| Texto | 2 050,6 |
| **Dataset** | **1 905,3** |
| Estudo | 1 569,6 |
| Galeria | 1 550,0 |
| Resultado | 43,3 |

**Os seis números batem à decimal com os do relatório**, e o `1 905,3` do Dataset está agora na
tabela e o `1 912,4` no rodapé — que é o item 5 do ciclo 11, fechado na ordem certa. O item de
desenho (cinco de seis painéis ficam mais vazios quando a tela cresce, enquanto o Resultado faz o
contrário) continua aberto e declarado.

### 5. Cor como sinal — **SOBREVIVE. Continua o melhor item da frente.**

`300 pares / 220 sob portão / 0 reprovados` nas duas polaridades × duas densidades, menor folga
**3,27:1** e **3,03:1**. Reproduzido por mim, número a número.

### 6. Tipografia da interface — **NÃO SOBREVIVE, e é a mesma causa do item 1**

A folha do produto tem **quatro** regras que trocam a fonte, e três aumentam o texto:

```
  QTabBar::tab:selected  { font-weight: bold }
  QGroupBox::title       { font-size: 12pt; font-weight: bold }     <- 21 px
  QHeaderView::section   { font-size: 12pt; font-weight: bold }     <- 21 px
  QLabel[apoio="true"]   { font-size: 8pt }
```

`widget.font()` continua devolvendo **Segoe UI 9 pt, não‑negrito** para todos eles. O produto
**sabe disso e escreveu**: o docstring de `ui/folha_de_estilo._escala_tipografica` diz que o QSS de
subcontrole *"é o que o Qt honra ao **pintar**"* e que a varredura *"é o que muda `QWidget.font()`,
que é onde o censo do crítico olha"*. O que ninguém fez foi a conta seguinte: a faixa reservada
para o título é `margin-top: linha px` — **4 px na compacta, 6 px na confortável** — e o título
pintado tem **21 px**. Duas linhas do mesmo arquivo (`ui/folha_de_estilo.py:340` e `:377`), uma
usando um token de **espaçamento** para reservar o lugar do outro, que sai da **escala
tipográfica**.

### 7. Controles — **SOBREVIVE, e é a conquista deste ciclo**

`0 sem nome, 0 sem papel, 0 nome vazio, 0 fora do Tab` nas 6 abas **e nas 13 telas de diálogo**,
nos seis arranjos. E os botões padrão saíram do inglês: **13 de 13** traduzidos, idempotente, e a
tabela cobre **18 de 18** `StandardButton` do Qt. Ver §4.2.

### 8. Estados vazios — **SOBREVIVE na janela; não existe nos diálogos**

`qt/vazio.EstadoVazio` — *"título, frase e o botão que resolve, dentro do vazio"* — é usado **4
vezes** na janela principal. Nos treze diálogos: **5 mostram uma vista vazia na tela e nenhum dos
cinco usa o componente**. `DialogoDePartidas` abre com uma grade de 878 px vazia e `0 partida(s)`
num canto. Não bloqueia; é a mesma forma do bloqueante que acabou de fechar, um andar abaixo.

### 9. A pele escura — **SOBREVIVE, e agora os diálogos estão nela**

Fotografei os treze diálogos nas **três** peles (39 PNG em `c13/dialogos/`) — o ciclo 12
fotografou **uma**. O cromo escuro dos diálogos está certo: fundo `#1a1d21`, campo com foco em
azul, marca de seleção legível, e nada de "claro invertido". O bloqueante do §3 aparece igual nas
três, o que confirma que ele é da densidade e não da pele.

---

## §2 — O bloqueante do ciclo 11, remedido pelas duas metades

### 2.1 Produto: **um** filtro, e ele alcança mais do que a lista

`qt/acessibilidade.vigiar_dialogos` instala **um** filtro de evento na aplicação e prepara todo
`QDialog` no `QEvent.Show`. `qt/janela.py` diz **uma linha** — conferido: o arquivo tem **1 883
linhas**, e `test_packaging.TamanhoDaJanelaTests.LIMITE` continua **1 883**. A catraca foi
derrubada durante o ciclo e **não foi afrouxada**; o código encolheu.

**A prova de que a decisão está no lugar certo é o que ela alcança sem ser avisada.** Montei as
oito formas de `QMessageBox` que o produto constrói (`campo.py:282`, `janela.py:1860` — a caixa de
*perder trabalho ao fechar* —, `painel_da_galeria.py:944` e `:1362`, `exportador.py:104`, e as
formas `information`/`critical`/`warning`) e o `QDialog` construído em linha em
`painel_de_estudo.py:1339` (S‑282, `ampliar_recorte`):

```
  `dialogos_do_produto()` devolve 12 classes.  'QMessageBox' esta nela? False

  tela                                             focav  s/nome  s/papel  fora Tab  botoes
  QMessageBox.question Yes|No  (campo.py:282)          3       0        0         0  Sim · Não
  QMessageBox Warning Yes|No   (janela.py:1860)        3       0        0         0  Sim · Não
  QMessageBox.question Ok|Cancel (galeria:944)         3       0        0         0  Confirmar · Cancelar
  QMessageBox Warning Ok|Cancel (galeria:1362)         3       0        0         0  Confirmar · Cancelar
  QMessageBox.information/critical/warning Ok          2       0        0         0  Confirmar
  QMessageBox 3 botoes a mao   (exportador.py:104)     4       0        0         0  Retomar de onde parou · Cancelar · Recomeçar do zero
  QDialog inline (Estudo | ampliar recorte)            1       0        0         0  Fechar
  ------------------------------------------------------------------------------------
  botoes de caixa de mensagem EM INGLES: 0 de 14      defeitos de nome/papel: 0
```

**Nenhuma dessas nove telas está na lista que o portão percorre, e todas as nove estão certas.**
Uma lista de doze chamadas espalhadas teria deixado as nove de fora. É a diferença entre fechar o
defeito e fechar a **forma** do defeito, e o construtor fechou a forma.

### 2.2 Arnês: a lista sai do produto, e a mutação (b) é minha

`c13_sabotar_o_achador.py`, escrevendo e apagando **um arquivo novo** em `qt/`:

```
  sha256 de qt/*.py ANTES : 804238d0a838e35a41b667b82048b79b7214959c317c156b58a6f637bd603179

  (b) 13o QDialog por heranca direta       o achador ve? True
      o portao: LEVANTOU -> RuntimeError: a lista de dialogos do arnes divergiu da do produto
                (qt.dialogos_do_produto): sem receita no arnes = ['_JanelaDeSondaC13']

  sha256 de qt/*.py DEPOIS: 804238d0a838e35a41b667b82048b79b7214959c317c156b58a6f637bd603179
  a pasta do tronco voltou identica: True     sobra alguma sonda? []
```

**A mutação que a ordem de serviço mandou eu testar passa.** O portão levanta, nomeia o diálogo, e
o tronco volta byte a byte.

**E ele tem três buracos, que eu abri e que não escondem defeito nenhum hoje** (§5, item 6): o
achador lê `class X(QDialog)` do texto, então `Base = QDialog; class X(Base)`, `class X(QMessageBox)`
e um `QDialog` num submódulo de `qt/` passam calados. O quarto buraco **existe no produto**: o
`QDialog(self)` de `ampliar_recorte` é uma **14ª tela** que nenhuma varredura sintática pode achar,
porque não é uma classe. Mediu‑se limpa (acima), e é por isso que isto é item de largura de
portão e não defeito de produto.

---

## §3 — Defeito bloqueante

### 1. O título do grupo é pintado a 12 pt na faixa que o Qt reservou para 9 pt, e o primeiro filho apaga a metade de baixo dele — 6 de 6 títulos na densidade Compacta, nas três peles

**Onde.** Janela principal, abas **Resultado, Estudo, Dataset e Galeria**. Densidade **Compacta**
— que é a densidade que a pele **`fita`** traz por padrão (`ui/pele.py:145`,
`Pele(FITA, "Fita", CROMO_FITA, densidade=COMPACTA)`) e que qualquer pessoa escolhe em
`Ver ▸ Densidade` em qualquer pele.

**O que.** `ui/folha_de_estilo.py:340` reserva a faixa do título com um token de **espaçamento**:

```python
f"QGroupBox {{ margin-top: {linha}px; ... }}"        # linha() = 4 px compacta, 6 px confortavel
```

e `ui/folha_de_estilo.py:377` manda **pintar** o título com um degrau da **escala tipográfica**:

```python
f"QGroupBox::title {{ font-size: {titulo}pt; font-weight: bold; }}"   # titulo = 12 pt -> 21 px
```

Os dois números nunca se encontram. O Qt calcula o topo do quadro com a fonte do **widget**
(9 pt), o primeiro filho sobe até lá, e a parte do título que ultrapassa a faixa fica **debaixo
dele**. Medido nos seis arranjos, a 1280, 1366 e 1920:

```
  === classica|foco|fita / compacta / 1280·1366·1920 px
      QGroupBox com titulo, visiveis: 6      titulos com a tinta COBERTA por um filho: 6 de 6
      [Resultado] Reconhecido (clique e arraste...)  margem= 9px  titulo=21px  COBERTO 3px  TabuleiroEditavel
      [Estudo   ] Lances                             margem= 9px  titulo=21px  COBERTO 8px  QTextBrowser
      [Estudo   ] Comentário do lance                margem= 9px  titulo=21px  COBERTO 8px  QTextEdit
      [Dataset  ] Filtros                            margem= 9px  titulo=21px  COBERTO 8px  QLabel, QLineEdit
      [Galeria  ] Cabeçalhos do PGN                  margem= 9px  titulo=21px  COBERTO 5px  QLabel, QLineEdit
      [Galeria  ] Este diagrama                      margem= 9px  titulo=21px  COBERTO 5px  BarraFluida

  === classica|foco|fita / confortavel / 1920 px
      titulos com a tinta COBERTA por um filho: 3 de 6      pior: 2 px  (abaixo do limiar do olho)
```

**8 px de 21 px é a metade de baixo da letra.** `Lances` e `Comentário do lance` leem‑se pela
metade de cima do desenho; o filete de dentro do grupo corta as letras ao meio.

**Como reproduzir.**

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
%PY% benchmarks\reports\critique\ui\c13\c13_titulo_de_grupo_coberto.py classica compacta 1920
%PY% benchmarks\reports\critique\ui\c13\c13_titulo_de_grupo_coberto.py classica confortavel 1920
%PY% benchmarks\reports\critique\ui\c13\c13_par_de_densidades.py classica compacta
%PY% benchmarks\reports\critique\ui\c13\c13_par_de_densidades.py classica confortavel
```

Os dois últimos gravam o par decisivo, **mesma pele, mesma largura, mesmo recorte de 260×26 px a
partir da origem do próprio grupo, só a densidade muda**:

* `z13_par_classica_confortavel_COMPOSTO.png` — `Lances` inteiro.
* `z13_par_classica_compacta_COMPOSTO.png` — `Lances` com a metade de baixo apagada.

E, sem nenhum instrumento meu, na captura **do construtor**:
`benchmarks/reports/ui/c12/capturas/c12_fita_1920x1080_estudo.png`, aba Estudo — recortada em
`z13_lances_amplo.png` e `z13_comentario_amplo.png`. E na do ciclo 10:
`benchmarks/reports/ui/c10/c10_fita_1920x1080_estudo.png` (`z13_c10_fita_lances.png`).

**Por que reprova.**

1. É o **primeiro item Visual** da carta §3.3, e ele é acionado duas vezes: *"Qualquer texto
   cortado, **sobreposto**..."*. Não é elisão com reticência — que é um recurso legítimo e é o que
   a coluna `Motivo` faz —, é tinta apagada por outro widget. Não há como o leitor recuperar o
   que sumiu.
2. **Não é preferência.** Três rótulos de painel das quatro abas mais usadas chegam à tela com
   um terço a metade de cada letra ausente, em **3 dos 6 arranjos** que esta frente declara
   percorrer, em todas as larguras que ela captura.
3. **É o décimo primeiro instrumento cego, e a cegueira é de uma espécie nova.** A régua de texto
   cortado que eu escrevi no ciclo 11 devolveu `0` em nove combinações e devolve `0` nos treze
   diálogos hoje — porque ela pergunta a largura a `w.fontMetrics()`, e a folha pinta outra fonte.
   O produto **documentou a diferença entre as duas fontes** e não fez a conta que ela obriga.
   Este é o mesmo padrão que reprovou os ciclos 9 e 11 (a medida certa sobre a população errada),
   num eixo que ninguém tinha olhado: **qual fonte**.
4. **Esteve fotografado três ciclos seguidos** — c10, c12 e a minha — e nenhum olho o pegou. O
   ciclo 12 inaugurou a prática certa (fotografar e olhar) e ela achou o `Close`; o mesmo conjunto
   de fotografias tinha isto.

*Alvo, cobrado por teste:* **0 de 6 títulos de grupo com tinta coberta, nas seis combinações de
pele × densidade e nas quatro larguras capturadas.** Hoje: **6 de 6 na compacta (pior 8 px de 21),
3 de 6 na confortável (2 px)**. O conserto natural é a faixa do título sair da mesma fonte que o
pinta — `margin-top` ≥ altura de `tipografia.escala(base)[TITULO]` — e não de `espaco.linha()`; e a
prova de vida é encolher `linha()` e ver o portão cair.

---

## §4 — Os dois julgamentos que a ordem de serviço pediu

### 4.1 A árvore limpa do `test_field_eval`: **o método se sustenta, e eu o conferi módulo a módulo**

Não aceitei a palavra. Conferi as cinco coisas que fazem uma "árvore limpa" ser limpa:

```
  o commit existe e e' alcancavel     git rev-parse f9-c12-arvore-limpa -> 7bcb396fed76...
  o pai dele e' o HEAD de hoje        parent 3a3228d3d7e5...   HEAD = 3a3228d  (intocado)
  nenhum ramo o contem                git branch --contains 7bcb396 -> vazio
  a arvore de trabalho temporaria     git worktree list -> nao esta' la'
  os 4 relatorios citam               code_commit = 7bcb396   code_dirty = False
```

E o que realmente importa — **o código medido é o código que os relatórios dizem que foi medido**:

```
  4 relatorios x 30 modulos medidos
     digest agregado publicado : 43f2ae26db1ef9ef
     digest agregado de HOJE   : 43f2ae26db1ef9ef        <- recalculado por mim, na arvore suja
     modulos cujo digest de hoje difere do publicado : 0 de 30 (nos quatro)
     modulos cujo CONTEUDO difere entre o tag e hoje  : 1 de 30 (inference.py)
        iguais depois de normalizar CRLF? True          <- so' fim de linha
```

**Os trinta módulos que a medição depende são, byte a byte, os de hoje.** O `dirty=false` é
verdadeiro porque a árvore era limpa de verdade, e o `commit` resolve porque a etiqueta o segura.

E o resultado fecha:

```
  tests/test_field_eval.py -> 101 passed, 142 subtests passed, 0 failed
  tronco inteiro           -> 3 failed, 4486 passed, 2 skipped, 4536 subtests em 325,5 s
      test_docs::test_a_arvore_do_README_lista_todo_modulo_do_pacote
      test_editor_model::SemTkinterTests::test_a_lista_cobre_todo_modulo_de_ui_que_hoje_dispensa_tkinter
      test_strings::AccentTests::test_no_ui_string_uses_an_unaccented_portuguese_word
```

**As três são as pré‑existentes, nenhuma é desta frente**, e o `4486` tem o `passed` a mais que o
ciclo 11 previu — é o `test_field_eval` que fechou. Item 6 do ciclo 11: **fechado, e por um método
que não reescreveu proveniência publicada.** Fica a ressalva declarada e não bloqueante: `7bcb396`
é alcançável por uma **etiqueta local**; num clone que não a receba, a proveniência dos quatro
relatórios aponta para um objeto que não existe.

### 4.2 O `Close` que o olho achou: **o conserto é maior que o achado, e trouxe um efeito colateral**

O construtor fotografou os diálogos pela primeira vez, viu um botão escrito `Close` e mediu
**7 de 12 botões padrão em inglês**. O conserto foi para o mesmo filtro do bloqueante, lendo
`ui/strings.BOTOES_PADRAO`, indexado pelo **nome do enum**. Testei os dois lados:

```
  (a) sem catalogo: 13 botoes padrao trocados de uma vez; segunda passada troca 0 (idempotente)
      OK · Save · Open · Retry · Abort · Close · Cancel · Discard · Help · Yes · No · Reset · Apply
      -> Confirmar · Salvar · Abrir · Tentar de novo · Interromper · Fechar · Cancelar · Descartar
         · Ajuda · Sim · Não · Restaurar · Aplicar
  (b) COM catalogo alemao instalado, o Qt desenha ['OK','Schließen','Abbrechen','Ja','Nein']
      depois do filtro                              ['Confirmar','Fechar','Cancelar','Sim','Não']
  (c) a tabela cobre 18 de 18 StandardButton do Qt: nenhum fica de fora
```

**Indexar pelo enum foi a decisão certa e ela paga**: o produto fala pt‑BR mesmo numa máquina cujo
Qt fala outra língua. E o alcance é maior do que os doze diálogos: as **catorze** legendas de botão
das oito formas de `QMessageBox` saem em português pelo mesmo caminho (§2.1).

**O que o julgamento tem de dizer sem atenuar:** o mesmo conserto **piorou 32 telas**. O PyQt6
desta árvore **já traz `qtbase_pt_BR.qm`**, e o catálogo do próprio Qt diz:

```
  enum      catalogo pt_BR do Qt     BOTOES_PADRAO do produto
  Ok        OK                       Confirmar        <- diverge, e e' o botao unico de 32 caixas
  Abort     Cancelar                 Interromper      <- diverge (o do produto e' melhor)
  Retry     Repetir                  Tentar de novo   <- diverge (empate)
  (os outros 10: identicos)
```

O produto tem **32** chamadas de `QMessageBox.information/critical/warning/about`, e todas têm um
botão só. Antes deste ciclo elas diziam `OK`; agora dizem **`Confirmar`** — inclusive a caixa
*Sobre o produto* e vinte e tantas caixas de erro (`"Não foi possível ler a base: ..."` →
`[Confirmar]`). Confirmar o quê? O argumento escrito é a régua `LETRAS_MINIMAS`, que nasceu no
ciclo 1 para reprovar `-`, `+` e `◀` — **glifos que não anunciam nada**. `OK` não é um glifo: é a
palavra que o Windows em pt‑BR usa, que o catálogo do próprio Qt usa e que todo leitor de tela
pronuncia. A régua de nome foi aplicada a texto desenhado e escreveu uma palavra errada em 32
telas. Não bloqueia (é uma palavra, não uma parede), mas é **regressão deste ciclo** e entra na
lista.

---

## §5 — Defeitos não bloqueantes

### 5.1 `Resultado` sai elidido no cabeçalho de `DialogoDePartidas`, nas três peles

```
  onde                                     titulo      pinta  regua diz  secao  a regua de C11 o viu?
  DialogoDePartidas (Galeria | Partidas)   Resultado      76         52     68  NAO -- ela diz que cabe
  DialogoDePartidas (Galeria | Partidas)   Lance          44         31     43  NAO -- ela diz que cabe
                                                                        (fita: secao 72, so' `Resultado`)
```

24 cabeçalhos medidos nas seis abas e nos treze diálogos; **2 elididos na clássica e na Foco, 1 na
fita**, e **0 nas abas**. A janela tem 878 px de cabeçalho e as colunas vizinhas têm 160 px de
folga cada: é política de largura de coluna que não pergunta ao desenho quanto ele mede.
Fotografado em `z13_cabecalho_partidas.png` — lê‑se **`Resultad·`**.
*Alvo: 0 de 24.*

### 5.2 `Ok → "Confirmar"` em 32 caixas de alerta

Ver §4.2. *Alvo: o botão único de uma caixa de aviso diz `OK` (ou `Fechar`), como o catálogo
pt‑BR do próprio Qt; `LETRAS_MINIMAS` deixa de valer para texto desenhado, ou ganha a exceção
escrita de que `OK` é palavra e não glifo.*

### 5.3 Nenhum dos treze diálogos usa o estado vazio do produto

```
  estados vazios (qt/vazio.EstadoVazio) na janela principal: 4
  dialogos com uma vista VAZIA na tela: 5     desses, com o componente: 0
     DialogoDePartidas · JanelaDeBusca (x2) · _JanelaDeColecao · _JanelaDePartidas
```

`DialogoDePartidas` abre com uma grade de 878×300 px vazia e um `0 partida(s)` num canto — carta
§3.3, *"Estado vazio sem orientação"*. `_JanelaDeColecao` diz `"0 partida(s) em colecao.pgn.
Escolha uma:"` sobre uma lista vazia — a frase se contradiz. `_JanelaDePartidas` é o bom exemplo:
tem a frase (`"Não há posição para procurar."`), mas não o botão que resolve.
*Alvo: as telas de diálogo que podem abrir vazias usam o mesmo componente das abas.*

### 5.4 `JanelaDeAtalhos` abre 12 px mais estreita que o próprio conteúdo

```
  [JanelaDeAtalhos] QScrollArea  janela 499x519  viewport 459px  rola H 12px  rola V 220px
```

Doze pixels: a linha `Ctrl+Shift+S` termina em `...no arquivo do editor (.cvt` e pede a barra
horizontal. Uma legenda de atalhos que rola para os lados é o pior lugar para uma barra
horizontal. *Alvo: 0 px de rolagem horizontal no tamanho em que a janela abre.*

### 5.5 O achador sintático de diálogos tem três buracos, e há uma 14ª tela hoje

```
  (b) 13o QDialog por heranca direta       ve? True    o portao LEVANTOU nomeando-o
  (d) `Base = QDialog` + `class X(Base)`   ve? False   o portao PASSOU calado
  (e) `class X(QMessageBox)`               ve? False   o portao PASSOU calado
  (f) QDialog em qt/<subpasta>/novo.py     ve? False   o portao PASSOU calado  (glob('*.py') nao recursivo)
```

E, no produto de hoje, `painel_de_estudo.py:1339` constrói um `QDialog(self)` **sem classe**
(S‑282, `ampliar_recorte`): uma tela real, que a pessoa abre pelo botão `Recorte`, que nenhuma
varredura sintática pode achar. **Ela está limpa** (1 focável, 0 sem nome, botão `Fechar`) —
porque o remédio mora no `QEvent.Show` e não na lista. É buraco de largura de portão, não defeito
de produto, e é por isso que não bloqueia. *Alvo: a frase que o portão publica diz "os N `QDialog`
que o produto **declara como classe**", e o número de telas medidas para de ser afirmado como o
total.*

### 5.6 Uma quinta e uma sexta E/S de disco na thread da janela

O item 13 do ciclo 11 pediu que a lista declarada cobrisse os caminhos que o perfil nomeia. O
perfil da minha execução nomeia dois que não estão nem no relatório nem no código:

```
  30,6 ms  <built-in method _sqlite3.connect>              <- painel_da_galeria.py:1106 _abrir_cache_de_posicoes
  28,6 ms  <method '__exit__' of 'sqlite3.Connection'>     <- painel_da_galeria.py:1106 _abrir_cache_de_posicoes
  14,4 ms  <method 'execute' of 'sqlite3.Connection'>      <- strings.py:431 _encurtar
   9,4 ms  <built-in method nt.stat>                       <- marcas.py:77 _marca_de
  92,3 ms  <built-in method ... fz_run_display_list>       <- painel_do_pdf.py:802 desenhar_pagina
```

A lista declarada nomeia quatro caminhos; o perfil nomeia seis. *Alvo: a lista cobre o que o perfil
nomeia.*

### 5.7 O portão de bloqueio continua reprovando, com os números de sempre

Três execuções internas, mediana reportada como a carta §6 exige:

```
  abrir PDF (load_pdf, 1a pagina a 300 DPI)   pior 240,7 ms   mediana 152,1 ms   [240,7 · 152,1 · 146,5]
  virar para a pagina 41                       97,1            86,9
  rasterizar pagina a 300 DPI                  68,6            62,9
  aba Dataset: mostrar e carregar as amostras  61,6            20,5
  ...  7 operacoes acima do piso de 16 ms     Veredito: REPROVOU
  parte DESTA FRENTE no pior: 4,9 ms de 243,2 ms perfilados (2,0 %)
```

Mesma ordem de grandeza do relatório (223,5 / 149,1). Aberto e declarado, como nos três ciclos
anteriores. **O filtro novo aparece no perfil e isso é honesto**: `<built-in method type>` a
**1,1 ms** de 133,4 ms, atribuído a `acessibilidade.py:220 eventFilter` — o preço de um filtro que
vê todo evento de todo objeto, medido e pequeno.

### 5.8 Miudezas medidas

* **`filtro`**, em minúscula, é o único rótulo de campo do produto que não começa com maiúscula
  (`DialogoDePartidas`). Todos os outros treze diálogos usam capitalização de frase.
* **`JanelaDeEstatisticas`** é um despejo monoespaçado (`classes:` / `peao: 1234` / `splits:`) num
  quadro de 560×520 px que fica ~90 % vazio, **sem título e sem botão nenhum** — a única das treze
  telas sem um botão para fechar. É a tela mais fraca do conjunto.
* **`DialogoDeTreino`** desenha uma barra **indeterminada** (`setRange(0, 0)`) para uma operação
  cujo total é conhecido: `ControladorDeTreino._progresso` escreve `"Treinando... época k/n"` na
  **mesma janela**, com numerador e denominador na mão. Carta §3.3: *"Barra de progresso
  indeterminada onde o total é conhecido"*. E a janela não tem botão de cancelar — quem cancela é
  o rodapé, o que é defensável porque ela não é modal (`show()`, não `exec()`), mas nada na tela
  diz isso.
* **`JanelaDeBusca`** empilha dois campos que não compartilham nem a borda esquerda (57 px contra
  78 px) nem a direita (505 px contra 396 px). Num formulário de duas linhas, as duas caixas
  deveriam dividir a mesma coluna.
* **Os que continuam abertos com os números de sempre, e eu confirmo:** `Motivo` ilegível
  (**17 / 24 / 25 de 27** a 1920 / 1366 / 1280); **0 de 5** cabeçalhos de fita desenhados na
  compacta (4 de 4 filetes; 5 de 5 no pleno a 1920); **6 de 24** botões de fita sem rótulo
  desenhado; tinta dos ícones **17,6 %–41,4 %** na grade de 16 px (amplitude **80,8 %**) e caixa
  **2×17 px** na fita confortável; **6 de 6** painéis acima de 200 kpx a 3840; marca da FEN só à
  direita.

---

## §6 — O que este ciclo conquistou, e eu confirmo com número

| o que o relatório afirma | o que eu medi |
|---|---|
| `c11_dialogos_prova.py` → `antes=0` (era 11) | **`antes=0, depois=0`**, instrumento meu, sem uma linha alterada |
| 6 arranjos: 216/216/240/240/360/360 + 46 em 13 diálogos, 0·0·0·0 | **idêntico, à unidade, nos seis** |
| mutação (b): o 13º `QDialog` derruba o portão | **LEVANTOU nomeando `_JanelaDeSondaC13`**; `sha256` de `qt/*.py` `804238d0…79` antes e depois |
| `dialogos_do_produto()` sem importar PyQt6 | **12 classes**, lidas da árvore sintática; o teste de deriva roda no venv sem Qt |
| 7 de 12 botões em inglês → 0 | **0 em 14** botões de `QMessageBox` também; **18 de 18** enums cobertos; idempotente; vence catálogo estrangeiro |
| fita: `topos [0,49] / alturas [43]` | **idêntico** nos seis arranjos; pleno `[0]` / `[81]` |
| 0 glifos de texto em todos os arranjos | **0**, nos seis |
| contraste 300 / 220 / 0; 3,27 e 3,03 | **idêntico** |
| `bloqueio.py` não reescreve `data/janela.json` | **`a8e53bd5…a1` antes e depois de 3 execuções**; `app_tkinter_state.json` com `mtime` 13:25 |
| Dataset a 4K = 1 905,3 kpx | **1 905,3**, e os outros cinco à decimal |
| `qt/janela.py` 1 883 linhas, catraca não afrouxada | **1 883**, `LIMITE = 1883` |
| `tests/unit/ui` 198 passed | **198 passed em 2,28 s** |
| nossa, sem `test_packaging.py`: 3 086 passed, 1 skipped, 0 failed | **3 086 passed, 1 skipped, 0 failed em 758,7 s**; o pulo é o de sempre (`test_fonts.py:333`, WOFF2 sem Brotli) |
| tronco 3 failed / 4 486 passed | **3 failed, 4 486 passed, 2 skipped, 4 536 subtests** |
| `test_field_eval` 101 passed | **101 passed, 142 subtests, 0 failed** |
| árvore limpa, 0 módulos diferentes | **digest publicado = digest de hoje**, 30 módulos, 0 diferentes; 1 difere só em CRLF |

**Quinze afirmações, quinze reproduzidas.** Não achei uma única medição que o relatório tenha
inflado, arredondado a favor ou publicado fora da ordem. O único número que eu vi divergir foi
**meu**, e a causa era a minha variável de fonte (Nota de procedimento).

E vale dizer o que este ciclo fez de estruturalmente melhor que os anteriores desta frente:

1. **A largura virou forma, e não lista.** O remédio no `QEvent.Show` alcança nove telas que
   nenhuma lista enumera — oito `QMessageBox` e um `QDialog` sem classe. Isso é fechar o *modo* de
   falhar, e não a instância.
2. **A mutação (b) é uma prova de vida de verdade**, e ela é a única defesa contra a terceira
   cegueira por largura. Rodei‑a; funciona; o tronco volta byte a byte.
3. **A catraca que ele quebrou, ele pagou** — encolheu o código em vez de baixar o corte.
4. **O `test_field_eval` fechou sem reescrever proveniência publicada**, e o método aguenta a
   auditoria módulo a módulo.
5. **Fotografar e olhar** entrou nesta frente e já pagou: achou um defeito de idioma que onze
   ciclos de régua não procuravam. A prática está certa; falta apontá‑la para as três peles e
   olhar o resto do quadro (§3).

---

## §7 — O que especificamente precisa mudar para eu aprovar

**Um item bloqueia. Só ele.**

1. **A faixa reservada ao título do `QGroupBox` passa a sair da fonte que o pinta.**
   `ui/folha_de_estilo.py:340` reserva `margin-top: espaco.linha()px` — **4 px na compacta, 6 px na
   confortável** — e `:377` manda pintar o título com `tipografia.escala(base)[TITULO]` = **12 pt =
   21 px**. Faça a primeira perguntar à segunda.
   *Alvo, cobrado por teste: **0 de 6** títulos de grupo com tinta coberta por um filho, nas seis
   combinações de pele × densidade e nas quatro larguras que `capture.TAMANHOS` fotografa. Hoje:
   **6 de 6 na compacta** (pior 8 px de 21, em `Lances`, `Comentário do lance` e `Filtros`) e
   **3 de 6 na confortável** (2 px). Prova de vida: encolher `espaco.linha()` em 1 px faz o portão
   cair, e aumentar `tipografia.escala(...)[TITULO]` em 1 pt também.*
   *E a segunda metade, que é o que torna isto estrutural:* **uma régua que meça texto com a fonte
   que a folha pinta**, e não com `QWidget.font()`. As quatro regras da folha que trocam a fonte
   estão listadas no §1.6; a régua tem de conhecê‑las. Com ela, o item 2 abaixo cai junto.

**Não bloqueiam, e entram no §9 da próxima ordem de serviço nesta ordem:**

2. **`Resultado` deixa de sair elidido no cabeçalho de `DialogoDePartidas`.** *Alvo: 0 de 24
   cabeçalhos de coluna elididos, medidos com a fonte pintada — hoje 2 (clássica e Foco) e 1
   (fita); `Resultado` pinta 76 px numa seção de 68 px, com 160 px de folga em cada coluna
   vizinha.*
3. **O botão único de uma caixa de aviso volta a dizer `OK`.** *Alvo: `BOTOES_PADRAO["Ok"]`
   concorda com `qtbase_pt_BR.qm`, que esta árvore já traz — hoje diverge, e a divergência sai
   desenhada em **32** chamadas de `information`/`critical`/`warning`/`about`. `LETRAS_MINIMAS`
   ganha a exceção escrita de que `OK` é palavra e não glifo, ou deixa de valer para texto
   desenhado.*
4. **As telas de diálogo que podem abrir vazias usam `qt/vazio.EstadoVazio`.** *Alvo: 5 de 5 — hoje
   0 de 5, contra 4 usos na janela principal. Comece por `DialogoDePartidas` (grade de 878×300 px
   vazia) e por `_JanelaDeColecao` (`"0 partida(s)... Escolha uma:"` sobre lista vazia).*
5. **`JanelaDeAtalhos` abre no tamanho do próprio conteúdo.** *Alvo: 0 px de rolagem horizontal —
   hoje 12 px, e a linha do `Ctrl+Shift+S` termina em `(.cvt`.*
6. **O portão para de afirmar mais largura do que tem.** *Alvo: a linha publicada diz "os N
   `QDialog` que o produto declara **como classe**" e nomeia o que a varredura sintática não
   alcança — hoje ela diz "os 12 `QDialog` que o produto declara" e o produto tem uma 14ª tela
   (`painel_de_estudo.py:1339`, S‑282) que nenhuma varredura sintática pode achar. As três
   sabotagens do §5.5 (`Base = QDialog`, `class X(QMessageBox)`, submódulo) são o mapa do buraco.*
7. **A barra do `DialogoDeTreino` fica determinada.** *Alvo: `setRange(0, n_epocas)` e o texto da
   época viram o mesmo número — hoje a barra é indeterminada e `ControladorDeTreino._progresso`
   escreve `"época k/n"` na mesma janela. E a janela diz onde se cancela.*
8. **A lista de E/S de disco declarada cobre o que o perfil nomeia.** *Alvo: 6 de 6 — hoje 4, e
   faltam `_sqlite3.connect` (30,6 ms) e `Connection.__exit__` (28,6 ms) em
   `painel_da_galeria.py:1106`, e `Connection.execute` (14,4 ms) em `strings.py:431`.*
9. **Os dois campos de `JanelaDeBusca` dividem a mesma coluna.** *Alvo: uma borda esquerda e uma
   direita — hoje 57 px contra 78 px à esquerda e 505 px contra 396 px à direita.*
10. **`filtro` vira `Filtro`.** *Alvo: 14 de 14 rótulos de campo com capitalização de frase — hoje
    13 de 14.*
11. **`JanelaDeEstatisticas` deixa de ser um despejo.** *Alvo: título, e um botão que fecha — hoje
    é a única das treze telas sem botão nenhum, com ~90 % de quadro vazio e o corpo em fonte
    monoespaçada.*
12. **Continuam abertos com os números de sempre, e nenhum precisa fechar para eu aprovar:**
    bloqueio > 16 ms (**7 operações, pior 240,7 ms, mediana 152,1 ms**, 2,0 % desta frente);
    `Motivo` (**17 / 24 / 25 de 27**); vazio de painel a 4K (**6 de 6 acima de 200 kpx**, pior
    3 104,2); **0 de 5** cabeçalhos de fita na compacta; **6 de 24** botões de fita sem rótulo;
    tinta dos ícones **17,6 %–41,4 %** e caixa **2×17 px**; **6 de 18** últimas linhas curtas;
    marca da FEN só à direita; a etiqueta local que segura `7bcb396`.

---

## §8 — Como reproduzir

```bat
set QT_QPA_PLATFORM=offscreen& set QT_QPA_FONTDIR=C:\Windows\Fonts
set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=<suite>\src;<tronco>\src
set C13=benchmarks\reports\critique\ui\c13
set PY=..\ChessVisionOFF_Puro\.venv\Scripts\python.exe

:: O BLOQUEANTE  (o par decisivo: mesma pele, mesma largura, so' a densidade muda)
%PY% %C13%\c13_titulo_de_grupo_coberto.py classica compacta 1920     :: 6 de 6 cobertos, pior 8 px
%PY% %C13%\c13_titulo_de_grupo_coberto.py classica confortavel 1920  :: 3 de 6, pior 2 px
%PY% %C13%\c13_par_de_densidades.py classica compacta                :: z13_par_..._COMPOSTO.png
%PY% %C13%\c13_par_de_densidades.py classica confortavel
%PY% %C13%\c13_recorte_do_grupo.py fita                              :: z13_composto_fita_*.png
:: e sem instrumento nenhum: benchmarks\reports\ui\c12\capturas\c12_fita_1920x1080_estudo.png

:: o bloqueante do ciclo 11, remedido
%PY% benchmarks\reports\critique\ui\c11\c11_dialogos_prova.py        :: antes=0  (era 11)
%PY% -m caissa.ui.audit.teclado --pdf "...\1937 Kemeri.pdf" --saida %C13%\gate_teclado
     :: 216/216/240/240/360/360 nas abas + 46 em 13 dialogos por arranjo; PASSOU nos seis
%PY% %C13%\c13_sabotar_o_achador.py     :: (b) LEVANTA nomeando; (d)(e)(f) passam calados
%PY% %C13%\c13_caixas_de_mensagem.py    :: 8 QMessageBox + 1 QDialog inline: 0 ingles, 0 sem nome

:: as reguas novas
%PY% %C13%\c13_fonte_pintada.py <pele> 1366        :: cabecalhos: 2 elididos que a regua de C11 nao ve
%PY% %C13%\c13_cabecalho_elidido.py classica       :: Resultado pede 76 px numa secao de 68
%PY% %C13%\c13_texto_cortado_nos_dialogos.py <pele>:: a regua de C11 nos 13 dialogos: 0 (ela le a fonte errada)
%PY% %C13%\c13_retrato_dos_dialogos.py <pele>      :: 13 PNG por pele, 39 no total

:: os portoes, remedidos
%PY% -m caissa.ui.audit.contraste --saida %C13%\gates   :: 300 / 220 / 0; 3,27 e 3,03. PASSOU
%PY% -m caissa.ui.audit.bloqueio  --pdf "..." --saida %C13%\gates  :: 7 ops; pior 240,7; mediana 152,1. REPROVOU
%PY% benchmarks\reports\ui\c12\c12_fita.py              :: topos [0,49] alturas [43]; 5/5 no pleno
%PY% benchmarks\reports\ui\c12\c12_icones_da_janela.py  :: 0 glifos nos 6 arranjos; 17,6-41,4 % / 80,8 %
%PY% benchmarks\reports\critique\ui\c5\c5_vazios.py benchmarks\reports\ui\c12\capturas\c12_claro_3840*.png
     :: Dataset 1 905,3 · Revisao 3 104,2 · Texto 2 050,6 · Estudo 1 569,6 · Galeria 1 550,0 · Resultado 43,3

:: a arvore limpa, conferida modulo a modulo
git rev-parse f9-c12-arvore-limpa & git cat-file -p f9-c12-arvore-limpa
git branch --contains 7bcb396          & git worktree list
<tronco>\.venv\Scripts\python.exe -m pytest tests\test_field_eval.py -q -p no:randomly  :: 101 passed
<tronco>\.venv\Scripts\python.exe -m pytest tests -q -p no:randomly  :: 3 failed, 4486 passed
.venv\Scripts\python.exe -m pytest tests\unit\ui -q                  :: 198 passed
.venv\Scripts\python.exe -m pytest tests -q --ignore=tests\integration\test_packaging.py
     :: 3086 passed, 1 skipped, 0 failed em 758,71 s
```

Artefatos meus, todos em `benchmarks\reports\critique\ui\c13\`: os dez instrumentos, `dialogos\`
(39 PNG — os treze diálogos nas três peles), `gate_teclado\` (7 JSON) e `gates\` (contraste e
bloqueio), os recortes `z13_*.png`, `BACKUP_janela_c13.json` e `sha_janela_antes.txt`. **Nada fora
desta pasta e deste documento foi escrito por mim.**

---

## §9 — Veredito

**REPROVADO — por um defeito, e ele é a metade da tipografia que nenhum instrumento desta frente
mede.**

Este é o ciclo em que o bloqueante fechou pelo caminho certo. Não fechou com doze chamadas; fechou
com **uma** decisão no `QEvent.Show`, e a diferença entre as duas formas é mensurável: a decisão
alcança **oito formas de `QMessageBox` e um `QDialog` construído em linha** — nove telas que a
lista do portão **não consegue enxergar** e que, mesmo assim, saem com `0 sem nome, 0 sem papel,
0 fora do Tab` e catorze botões em português. Rodei o meu próprio instrumento do ciclo 11 sem
alterar uma linha: **11 → 0**. Rodei a mutação que a ordem de serviço mandou eu rodar: um 13º
`QDialog` entra no produto e **o portão levanta nomeando‑o**, com `qt/*.py` byte a byte igual
antes e depois. Reproduzi quinze afirmações do relatório e as quinze bateram — inclusive a
árvore limpa do `test_field_eval`, que eu conferi **módulo a módulo**: trinta módulos, digest
publicado igual ao de hoje, `dirty=false` verdadeiro, `HEAD` e ramos intocados. O único número
que divergiu na sessão foi o **meu**, por uma variável de fonte que eu escrevi errado.

E este é o ciclo em que a prática certa entrou nesta frente: **fotografar os diálogos e olhar**.
Ela achou de primeira um defeito que onze ciclos de régua não procuravam — sete de doze botões em
inglês num produto em pt‑BR. Isso responde sozinho a pergunta que a ordem de serviço fez sobre a
cobertura dos portões existentes: nenhuma régua vale mais do que abrir a tela e olhar, e esta
frente passou onze ciclos medindo o que já sabia medir.

Não aprovo porque o mesmo conjunto de fotografias tinha outra coisa, e ela é maior. Na densidade
**Compacta** — a que a pele `fita` traz por padrão e que qualquer pessoa escolhe em
`Ver ▸ Densidade` —, **6 de 6 títulos de grupo** das quatro abas mais usadas são pintados com **8
px dos seus 21 px debaixo do primeiro filho do próprio grupo**. `Lances`, `Comentário do lance` e
`Filtros` chegam à tela com a metade de baixo de cada letra apagada. Está na captura do construtor
do ciclo 12 e na do ciclo 10, e o par que eu gravei — mesma pele, mesma largura, mesmo recorte, só
a densidade muda — mostra o mesmo rótulo inteiro de um lado e cortado do outro.

A causa é uma linha conversando com outra do mesmo arquivo: `ui/folha_de_estilo.py:340` reserva a
faixa do título com `espaco.linha()` — um token de **espaçamento**, 4 px — e `:377` manda pintá‑lo
com `tipografia.escala(base)[TITULO]` — um degrau da **escala tipográfica**, 12 pt, 21 px. E a
razão de nenhum portão ter visto é o décimo primeiro modo de cegueira desta frente, e ele é de uma
espécie que ainda não tinha aparecido. Os dez anteriores erraram a **regra**, a **pele**, a
**janela** e o **arquivo**. Este erra a **fonte**: toda régua daqui pergunta a medida do texto a
`QWidget.fontMetrics()`, e a tela pinta a fonte da folha de estilo. A minha própria régua de texto
cortado do ciclo 11 devolve `0` — e devolve `0` também nos treze diálogos — porque mede 9 pt onde
o Qt desenha 12 pt negrito, 46 % mais largo e 31 % mais alto. O produto **documentou** que as duas
fontes são diferentes, no docstring de `_escala_tipografica`, e nomeou o censo do crítico como
quem olha a errada. Escreveu o diagnóstico e não fez a conta.

Feito o item 1 do §7 — a faixa do título saindo da fonte que o pinta, e uma régua que meça texto
com a fonte que a folha desenha —, **aprovo**. Os onze itens restantes são desenho, palavra e
disciplina de instrumento; nenhum deles apaga metade de uma letra na tela.
