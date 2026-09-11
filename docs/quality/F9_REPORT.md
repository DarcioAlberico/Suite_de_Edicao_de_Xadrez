# F9 — Interface unificada: auditoria, correções e portões medidos

> **Data:** 2026-09-07 · **Frente:** F9 (Interface) · **Alvo:** SPEC §10 e §11.3
> **Máquina:** Windows 11, Ryzen 5 8400F, PyQt6 6.11 / Qt 6.11, Python 3.10 (venv do tronco)
> **Livro da medição:** `1937 Kemeri.pdf` (289 páginas, digitalização de 1937)

---

## 0. Veredito por portão

| Portão (SPEC §11.3 / §10) | Antes | Depois | Instrumento |
|---|---|---|---|
| **Contraste WCAG AA em 100 % dos pares, nas duas peles** | 45 (clara) + 52 (escura) pares reprovados | **0 e 0**, em 286 pares por pele (212 sob portão) | `caissa.ui.audit.contraste` |
| **Pan/zoom ≥ 55 fps sustentados a 300 DPI** | não medido | **78,0 fps @ p95** (mediana de 4 invocações × 3 execuções) | `caissa.ui.audit.quadros` |
| **Navegação inteira por teclado, nome e papel em todo controle** | 40 controles sem nome, 3 sem papel, 6 abas reprovando | **256/256 alcançáveis, 0 sem nome, 0 sem papel, 6/6 abas** | `caissa.ui.audit.teclado` |
| **Tema escuro projetado, não invertido** | afirmação | **18 asserções numéricas** (elevação, matiz, negativo exato) | `tests/unit/ui/test_tema_escuro.py` |
| **Nada bloqueia a thread da interface por mais de 16 ms** | não medido | **REPROVA: 244 ms ao abrir, 178 ms por virada de página** | `caissa.ui.audit.bloqueio` |
| **Progresso real, nunca indeterminado quando o total é conhecido** | não medido | **REPROVA: 1 operação** (detecção de duplicatas) | `caissa.ui.audit.progresso` |

**Dois portões continuam reprovando, e os dois estão fora da fronteira desta frente.** A causa de
ambos é a mesma: a rasterização da página e a deduplicação do dataset rodam onde não deviam, e o
conserto mora em arquivos que a F9 não pode tocar (`pdf_io.py`, `audit.py`) ou exige refazer o
contrato síncrono de `PainelDoPdf.desenhar_pagina`, de que 48 referências em `src/` e `tests/`
dependem. **§7 registra a medição, a pilha e o caminho do conserto.** Reportar o número é o
que esta frente devia fazer; consertá-lo às pressas, quebrando 4.400 testes, não.

### Suítes

| Suíte | Antes (medido no início) | Depois |
|---|---|---|
| Tronco (`ChessVisionOFF_Puro`) | 4407 passaram, **5 falharam**, 2 puladas, 4300 subtestes | **4409 passaram, 3 falharam**, 2 puladas, 4301 subtestes |
| Suíte, exceto `tests/unit/typeset/` | — | **2649 passaram, 0 falharam** |
| Suíte, completa | 2779 passaram, 1 pulada, 2 xfailed | 2860 passaram, **9 falharam** em `tests/unit/typeset/` |

**O tronco melhorou: 5 → 3 falhas.** As três que restam são anteriores a esta frente e nenhuma é
de interface — vêm de arquivos que outras frentes acrescentaram sem registrar nas listas que o
tronco vigia (`biblioteca.py`, `cortina.py`, `selecao_de_area.py`, `substituicao.py`,
`desenho_de_diagrama.py`, `pdf_substituicao.py`). As duas que sumiram são de `test_ui_estilos`, e
eram do trabalho anterior **nesta mesma frente**: a face dos dois papéis de ênfase estava
declarada em `qt/tema.py` sem a isenção correspondente, e a mudança para `ui/folha_de_estilo.py`
levou a isenção junto.

**As 9 falhas da suíte completa são todas de `tests/unit/typeset/` e não são desta frente.** A
prova é dupla: a suíte inteira **menos** aquele diretório fecha em **2649 passaram, zero
falharam**; e `src/caissa/typeset/board_svg.py`, `latex.py`, `typography.py` e `figurine.py` foram
modificados **durante** esta sessão (15:42 a 16:15) por outra frente em curso — a F9 não tocou em
`src/caissa/` fora de `src/caissa/ui/`. Os 83 testes novos estão todos verdes.

---

## 1. Como esta auditoria foi feita

A carta dos críticos (§3.1) manda **olhar**, e (§6) manda **remedir**. As duas coisas exigem
instrumentos, e não afirmações:

```
# as 24 capturas: 6 abas x 2 peles x 2 tamanhos
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
PYTHONPATH="<tronco>/src;<suite>/src" <tronco>/.venv/Scripts/python.exe \
  -m caissa.ui.audit.capture --saida benchmarks/reports/ui --marca depois --pdf "<livro>.pdf"

# a prancha de controles, nos estados que a tela feliz não tem
  -m caissa.ui.audit.amostrario --saida benchmarks/reports/ui

# os quatro portões numéricos
  -m caissa.ui.audit.contraste                 # roda em qualquer venv, sem Qt
  -m caissa.ui.audit.teclado  --pdf "<livro>.pdf"
  -m caissa.ui.audit.quadros  --pdf "<livro>.pdf"
  -m caissa.ui.audit.bloqueio --pdf "<livro>.pdf"
  -m caissa.ui.audit.progresso                 # roda em qualquer venv, sem Qt
```

Saídas em `benchmarks/reports/ui/`: 24 PNGs `antes_*` e 24 `depois_*`, dois `amostrario_*`, e os
JSON `contraste.json`, `teclado.json`, `fps_*.json`, `bloqueio_*.json`, `progresso_*.json`.

**`QT_QPA_FONTDIR` não é detalhe.** Sem ela o `offscreen` do Windows sobe com **zero** famílias de
fonte: todo glifo vira caixa e a métrica de texto passa a ser a da fonte de reserva. "Resultado"
mede 117 px sem a variável e 52 px com ela. Uma captura sem fontes não mostra a janela, e um teste
de leiaute sem fontes afirma larguras que não existem em máquina nenhuma.

### O que "as duas peles" significa neste produto

A janela tem **três peles** (`ui/pele.py`), e o cromo escuro é propriedade de uma delas ("Foco").
As capturas `depois_claro_*` são a pele **Clássica** e as `depois_escuro_*` são a **Foco**, que
além da paleta traz um arranjo de cromo diferente (a fila de pílulas no topo). **Isso mistura dois
eixos**, e por isso a comparação de *paleta* não é feita nas capturas do produto: ela é feita na
prancha de controles (`amostrario_claro.png` / `amostrario_escuro.png`), que é o mesmo arranjo nas
duas paletas, com os estados que uma captura de produto não pega por acaso — foco, desabilitado,
tri-estado, seleção.

---

## 2. A auditoria: tabela de defeitos

Severidade: **B** = bloqueante pela carta §3.3 (reprova sozinho) · **A** = alto · **M** = médio ·
**O** = observação registrada, não corrigida.

| # | Aba | Pele | Tamanho | Defeito | Sev. | Estado |
|---|---|---|---|---|---|---|
| D1 | Galeria | escura | 1280×800 | **"Copiar link" desenhado como "opiar linl"** — 11 controles num `QHBoxLayout` que não cabe, e o Qt espreme o último até cortar o rótulo dos dois lados | **B** | corrigido |
| D2 | Galeria | ambas | ambos | **Glifo inexistente**: `⏮`/`⏭` (U+23EE/23ED) não existem na Segoe UI — dois dos quatro botões de navegação desenhavam uma **caixa vazia** | **B** | corrigido |
| D3 | Dataset | ambas | ambos | **Cabeçalho cortado**: a coluna de conjunto escrita `"Conjunt"` — 55 px declarados para um título que pede 64 | **B** | corrigido |
| D4 | Dataset | ambas | ambos | **Conteúdo cortado**: a coluna "Lado" com 45 px mostrando `"Bran…"` em 5.431 linhas, ao lado de uma coluna "Livro" de 150 px em que toda célula diz "—" | **B** | corrigido |
| D5 | todas | ambas | ambos | **Contraste**: 45 pares abaixo do piso na pele clara e 52 na escura (§3) | **B** | corrigido |
| D6 | todas | escura | ambos | **Ícone e rótulo em cores opostas no mesmo botão**: o disquete de "Salvar a posição" saía branco sobre a face azul-clara do primário, ao lado de um rótulo quase preto — o ícone a 1,7:1 da face em que estava | **B** | corrigido |
| D7 | todas | ambas | ambos | **Duas cores de "selecionado" na mesma janela**: a lista no azul de fábrica do Windows, a tabela no `SELECAO` da folha (fotografado em `amostrario_claro.png`) | **B** | corrigido |
| D8 | Texto | ambas | ambos | **Estado vazio sem orientação**: 940×880 px de retângulo branco, sem uma palavra | **B** | corrigido |
| D9 | todas | ambas | ambos | **Sem nome acessível**: 40 controles (12 campos, 6 réguas, 5 escolhas, 3 editores, 2 tabelas) anunciados pelo leitor de tela como o tipo, sem dizer qual | **A** | corrigido |
| D10 | todas | ambas | ambos | **Anel de foco lido como barra cheia**: o retângulo de foco da régua encostava no trilho azul | **M** | corrigido |
| D11 | Resultado | ambas | ambos | **Peça invisível no glifo de reserva**: `GLIFO_CLARO` sobre `CASA_CLARA` dá **1,29:1** — a peça branca desenhada e ausente em 32 das 64 casas | **A** | corrigido |
| D12 | Galeria | ambas | ambos | **Barra indeterminada com o total à vista**: a detecção de duplicatas escreve `f"{len(rotulos)} imagem(ns)"` no rodapé e não passa o número à barra; e não é cancelável | **B** | **§7.2** |
| D13 | todas | ambas | ambos | **Janela trava ~178 ms por virada de página e 244 ms ao abrir** — a rasterização a 300 DPI roda na thread da interface | **B** | **§7.1** |
| D14 | todas | ambas | ambos | **A janela não encolhe abaixo de 1243×890** (clara) / 1243×924 (escura): não cabe num 1366×768 | **A** | **§7.3** |
| D15 | Resultado | clara | 1920×1080 | O tabuleiro para em 560 px e deixa ~430 px de moldura escura de cada lado; a metade de baixo do painel fica vazia | **O** | §7.4 |
| D16 | Resultado | clara | ambos | A moldura do tabuleiro é `#312e2b` (marrom escuro) também na pele clara — decisão declarada da S-224 (o documento não segue a pele), registrada aqui porque um crítico a verá antes de ler a decisão | **O** | — |
| D17 | Dataset | ambas | ambos | As colunas de arquivo e FEN continuam elididas com `…` — conteúdo genuinamente maior que qualquer largura razoável | **O** | — |
| D19 | visor | ambas | — | **O zoom opera a ~7 % acima do piso de 55 fps** (mediana 59,0; uma de quatro invocações deu 54,0) — o pan tem oito vezes de folga, o zoom tem meia | **O** | §6.1 |
| D18 | prancha | ambas | — | O texto de porcentagem de `QProgressBar` cruzaria o preenchimento; o produto o esconde (`qt/rodape.py:126`, `setTextVisible(False)`), a prancha não | **O** | §7.5 |

---

## 3. Contraste — o portão duro

### 3.1 O instrumento, e por que ele não é uma lista

Um checador que recebe uma lista de pares escrita à mão mede a diligência de quem a escreveu: o
par esquecido é justamente o que reprova. Aqui a lista é **derivada de quatro fontes**, e nenhuma
delas é uma opinião:

| Origem | Pares (por pele) | Como são derivados |
|---|---|---|
| `folha` | 243 | a folha de estilo é analisada e a **cascata do Qt é resolvida** — herança de classe, subpeça, estado, seletor descendente — para descobrir sobre que fundo cada `color:` de fato cai |
| `paleta` | 22 | de `ui/folha_de_estilo.PAPEIS_DA_PALETA`, que é o mapa que a janela aplica |
| `marcacao` | 15 | de `tokens.SIGNIFICADO`, a tabela em que cada marcação declara a superfície dela |
| `tabuleiro` | 6 | corpo e traço de cada glifo contra as três cores de casa |
| **total** | **286** | 212 sob portão, 74 isentos e **todos com o motivo escrito** |

Um componente novo na folha vira par novo no relatório sem que ninguém escreva uma linha no
checador. `tests/unit/ui/test_cascata.py` afirma o motor contra folhas minúsculas escritas à mão,
porque é ali que um portão de contraste mente sem que ninguém veja: se a resolução do fundo
estiver errada, cada par continua sendo medido — contra a cor errada.

### 3.2 Os quatro pisos e as três isenções

| espécie | piso | critério |
|---|---|---|
| `texto` | 4,5:1 | WCAG 2.1 AA, 1.4.3 |
| `foco` | 3,0:1 | WCAG 2.4.11 / 1.4.11 |
| `borda` (limite de componente) | 3,0:1 | WCAG 1.4.11 |
| `grafico` (preenchimento, marcação, estado) | 3,0:1 | WCAG 1.4.11 |

**As isenções, declaradas antes que alguém as descubra:**

1. **`:disabled` não é portão** — a WCAG isenta componente inativo em 1.4.3 e 1.4.11. Eles
   continuam medidos e aparecem no relatório com a razão e o motivo; neste produto passariam de
   qualquer forma, porque o texto morto é `TEXTO_SECUNDARIO`.
2. **`SEPARADOR` é hierarquia, não informação** — é a única cor deliberadamente abaixo de qualquer
   piso (1,39:1 na clara, 1,47:1 na escura). O reconhecimento é **por valor**: compara-se o
   hexadecimal com o que `tokens.cor(SEPARADOR)` devolve, para que ninguém isente uma borda de
   verdade escrevendo "separador" nela.
3. **`:hover` e `:pressed` não são portão para *borda*, e **são** para *texto*.** A 1.4.11 fala de
   estados de componente, e a leitura razoável é a persistente (`checked`, `selected`, `focus`); um
   realce discreto sob o ponteiro é o que toda ferramenta profissional usa. O **rótulo** desses
   estados continua sendo portão, e foi exatamente ali que estava o defeito (§3.3, item 1).

**O `max` do limite de componente, e por que ele não é uma folga.** A primeira versão do checador
media a borda contra a própria face *e* contra o painel, e reprovava vinte pares em que a borda
sumia dentro do botão — o que não é defeito: uma borda que se funde ao preenchimento faz o
preenchimento parecer um pouco maior, e o controle continua se lendo contra o painel. A 1.4.11
pede que *alguma* informação visual que identifique o componente esteja a 3:1 das cores
adjacentes; não pede que todas estejam. O par reportado é o melhor dos dois caminhos, e **a nota
carrega o número perdedor** para ninguém precisar acreditar no `max`.

### 3.3 Os defeitos que a medição achou, e o que mudou

| # | Par | Antes | Depois | Correção |
|---|---|---|---|---|
| 1 | rótulo do **botão primário sob o ponteiro** (`#ffffff` sobre a face clareada) | **4,47:1** · pressionado **3,09:1** | 6,1:1 · 7,3:1 | O realce misturava a face **com a letra** — literalmente a direção que apaga o texto. `tokens.afastar` inverte o sentido: escurece no tema claro, clareia no escuro, e o contraste do rótulo **sobe** com o realce |
| 2 | rótulo do **destrutivo sob o ponteiro** | 3,79:1 · pressionado 3,00:1 | 6,4:1 · 7,4:1 | idem |
| 3 | **seleção contra o poço da lista** | 1,63:1 (clara) · 1,85:1 (escura) | **4,86:1** · **3,72:1** | `SELECAO` deixou de ser um azul pálido e passou a ser sólido (`#1e6ad7` / `#3f73b8`), com letra branca. É a seleção que Affinity e Resolve desenham, e é a única que passa o piso |
| 4 | **borda do controle pressionado contra o painel** | 2,56:1 (clara) · 2,07:1 (escura) | 3,97:1 · 5,81:1 | `CONTORNO_DE_CROMO` re-derivado por busca sobre as **cinco** superfícies de cromo, com folga |
| 5 | **polegar da régua contra o trilho** | 1,20:1 pelo corpo, 2,56:1 pela borda | **6,03:1** · 7,64:1 | o polegar ganhou borda em `TEXTO_SECUNDARIO`, que é o cinza já medido da S-146 |
| 6 | **borda do botão de ênfase desabilitado** | 1,04:1 (`MOLDURA` sobre o painel escuro) | 1,47:1, isento e nomeado | `MOLDURA` é superfície de **documento** servindo de borda de controle — o defeito que a S-145 existe para não ter. Passou a `SEPARADOR`, e as duas regras redundantes que a corrigiam pela cascata saíram |
| 7 | **peça branca sobre casa clara** (glifo de reserva) | **1,29:1** | **13,4:1** pelo traço | o glifo passou a ser desenhado com `QPainterPath` e contorno na cor do outro glifo — a solução do xadrez impresso desde sempre, sem cor nova |
| 8 | **item de menu selecionado sobre a face do menu** (escura) | 2,75:1 | 5,26:1 pela borda | a aritmética prova que não há saída por cor: uma seleção 3:1 acima de `#2c3036` exige L ≥ 0,191, e um branco a 4,5:1 sobre ela exige L ≤ 0,183 — os intervalos não se cruzam. O limite passou a ser a borda de foco, que é como a 1.4.11 pede que se resolva |

**Resultado.** 286 pares por pele, 212 sob portão, **zero reprovados nas duas**. A menor folga é
**3,03:1 contra piso 3,0** (polegar da rolagem sobre o trilho, pele escura) e **3,27:1** (marcação
`PROBLEMA` sobre a casa escura, pele clara).

### 3.4 Os cinco pares mais apertados de cada pele

| Pele | Razão | Piso | Par |
|---|---|---|---|
| clara | 3,27:1 | 3,0 | marcação `PROBLEMA` sobre a casa escura |
| clara | 3,27:1 | 3,0 | marcação `ALVO` sobre a casa escura |
| clara | 3,28:1 | 3,0 | marcação `DIVERGENTE` sobre a casa escura |
| clara | 3,54:1 | 3,0 | `QScrollBar::handle` sobre o trilho |
| clara | 3,62:1 | 3,0 | marcação `CORRIGIDO` sobre a casa escura |
| escura | 3,03:1 | 3,0 | `QScrollBar::handle` sobre o trilho |
| escura | 3,27:1 | 3,0 | marcação `PROBLEMA` sobre a casa escura |
| escura | 3,27:1 | 3,0 | marcação `ALVO` sobre a casa escura |
| escura | 3,35:1 | 3,0 | item selecionado contra o item em repouso |
| escura | 3,35:1 | 3,0 | seção de cabeçalho selecionada contra a em repouso |

---

## 4. O tema escuro é projetado, e a prova é numérica

"Tema escuro que é só o claro invertido" é o único item do §3.3 que **não dá para ver numa
captura** — um tema invertido parece um tema escuro. O que o denuncia são três propriedades, e
`tests/unit/ui/test_tema_escuro.py` afirma as três:

1. **A elevação inverte de sentido.** Na paleta clara o poço do campo é **mais claro** que o
   painel (`#f8f9fb` > `#f0f0f0`); na escura ele é **mais escuro** (`#15171a` < `#1f2124`),
   enquanto o botão sobe nas duas. Uma inversão mecânica não consegue produzir isso: ela preserva
   a ordem relativa das luminâncias, e o poço continuaria acima do painel. É o tique
   inconfundível de paleta invertida, e ele não está aqui.
2. **A matiz sobrevive.** Uma inversão de canal (`255 - c`) roda a matiz em ~180°: o vermelho de
   "pare" viraria ciano. Medido nos nove papéis com matiz, o desvio máximo entre as duas paletas
   é de **2°** — `PROBLEMA_TEXTO` continua vermelho, `PRONTO_TEXTO` continua verde, e o que muda
   é a luminosidade, o mínimo para cruzar o piso.
3. **Nenhum papel de cromo é o negativo exato do outro**, canal a canal, com tolerância de 2 %.
   É a definição literal de "invertido", excluída papel por papel em vez de por leitura.

E a quarta, que é do produto e não da paleta: **o documento não segue a pele**. A folha do livro,
o tabuleiro e as três cores de casa têm o mesmo valor nas duas — porque o produto é comparar um
diagrama impresso em papel branco com o que o modelo leu, e as doze marcações foram calibradas
contra esse fundo (S-224).

---

## 5. Teclado e acessibilidade

### 5.1 O instrumento

O arnês **anda** pela janela como um teclado andaria: `QWidget.focusNextPrevChild(True)` em laço é
exatamente o que o Qt chama quando a tecla é apertada, com as regras de `focusPolicy`, de
`setTabOrder` e de procurador de foco que a janela montou. Um `QKeyEvent` sintético mediria outra
coisa — "a tecla foi entregue" —, porque numa janela com paleta de comandos ele pode ser consumido
por um filtro antes de chegar ao gerenciador de foco.

Três isenções, e cada uma é a regra da plataforma e não uma folga:

- **controle desabilitado** sai da cadeia do `Tab` de propósito, em todo sistema;
- **botão de grupo exclusivo não marcado** é alcançado pelas **setas** — um grupo de rádio é *um*
  ponto de parada, não seis;
- **texto selecionável com `ClickFocus`** fica fora da cadeia por decisão do Qt; o conteúdo chega
  ao leitor de tela pela árvore de acessibilidade, com o nome que ele tem. A isenção exige
  **também** o papel não interativo: um *botão* com `ClickFocus` continua sendo defeito.

### 5.2 O resultado

| Aba | Focáveis | Alcançados | A volta fecha | Sem nome | Sem papel | Veredito |
|---|---|---|---|---|---|---|
| Resultado | 29 | 29 | sim | 0 | 0 | PASSOU |
| Estudo | 56 | 56 | sim | 0 | 0 | PASSOU |
| Revisão | 34 | 34 | sim | 0 | 0 | PASSOU |
| Texto | 42 | 42 | sim | 0 | 0 | PASSOU |
| Dataset | 42 | 42 | sim | 0 | 0 | PASSOU |
| Galeria | 53 | 53 | sim | 0 | 0 | PASSOU |
| **total** | **256** | **256** | 6/6 | **0** | **0** | **PASSOU** |

**Antes eram 40 controles sem nome nenhum** — doze `QLineEdit`, seis réguas de zoom, cinco caixas
de escolha, três editores, duas tabelas. O Qt anunciava cada um pelo tipo: "caixa de edição", sem
dizer qual.

**O conserto é uma varredura, e não vinte chamadas.** O texto que descreve cada campo já está na
tela, ao lado dele; o que faltava era a **ligação**, que o Qt só faz sozinha num `QFormLayout`.
`qt/acessibilidade.nomear_tudo` percorre a árvore uma vez no fim da montagem e aplica a cascata
que `ui/nomes_acessiveis.py` declara: `accessibleName` posto à mão → `text()` → primeira linha da
dica → rótulo vizinho no leiaute (por `buddy` ou por posição) → nome declarado por classe. Vinte
chamadas espalhadas seriam vinte lugares para lembrar, e a vigésima primeira — o campo que o
próximo item acrescentar — nasceria muda.

**`PyQt6` não empacota `QAccessible`** (conferido: o nome não existe em `QtGui`, `QtWidgets` nem
`QtCore`), então o papel é derivado de `teclado.PAPEL_POR_CLASSE`, a tabela do que o
`QAccessibleWidget` de cada classe reporta ao sistema. Perguntar ao Qt seria melhor; não perguntar
seria não medir.

---

## 6. Desempenho medido

### 6.1 Pan e zoom — **PASSA**

`1937 Kemeri.pdf`, página 41, **300 DPI** (1633×2468 px), área visível 1244×669 px. A carta dos
críticos (§6) exige três execuções; o arnês faz três por invocação e reporta a **execução mediana
inteira**, e ele foi invocado **quatro vezes** com a máquina ociosa. A execução mediana da
invocação mediana:

| gesto | quadros | média | mediana | p95 | p99 | pior | **fps @ p95** | > 16 ms | veredito |
|---|---|---|---|---|---|---|---|---|---|
| pan | 120 | 1,61 ms | 1,74 | 2,24 | 2,67 | 2,70 | **446,7** | 0,0 % | PASSOU |
| zoom | 60 | 8,42 ms | 6,73 | 18,50 | 20,37 | 20,37 | **54,0** | 11,7 % | marginal |
| juntos | 180 | 3,28 ms | 1,57 | 13,12 | 17,70 | 19,63 | **76,2** | 1,7 % | PASSOU |

**As quatro invocações, para a variância ficar à vista em vez de escondida na mediana:**

| invocação | pan | zoom | **juntos** |
|---|---|---|---|
| A | 446,7 | 54,0 | 76,2 |
| B | 433,6 | 59,1 | 78,7 |
| C | 433,9 | 62,3 | 77,4 |
| D | 469,7 | 58,8 | 78,5 |
| **mediana** | **440** | **59,0** | **78,0** |

**O portão é "pan/zoom", e ele passa com 78,0 fps @ p95 contra o piso de 55.** Mas o número que
importa dizer é outro: **o zoom sozinho mediana 59,0 e caiu a 54,0 em uma das quatro invocações**
— ele opera a ~7 % acima do piso, e é o componente que a próxima mexida no visor pode derrubar. O
pan tem oito vezes de folga; o zoom tem meia. Um relatório que publicasse só os 78 estaria
publicando a metade tranquila da medição.

**E um aviso sobre a máquina.** Uma medição feita enquanto a suíte de 2.800 testes rodava em
paralelo deu **53,6 fps** no conjunto — abaixo do piso. Ela não está na tabela porque medir uma
janela sob carga de compilação mede o agendador do sistema; está registrada aqui porque a
diferença entre 53,6 e 78,0 é a mesma medição em duas condições, e quem for remedir precisa saber
disso antes de concluir qualquer coisa.

**Três decisões de medição, cada uma respondendo a um jeito de mentir.** `repaint()` e nunca
`update()` (um laço de `update()` mede a velocidade de *agendar* e reportaria dezenas de milhares
de fps sobre uma janela que engasga); o relógio envolve o **gesto e** a repintura (o zoom invalida
a escala e quem paga é a repintura seguinte); e o fps sai do **p95**, não da média — a média de 60
quadros com 6 travadas continua bonita, e o que a pessoa vê é a travada.

**O que fica de fora, dito antes que alguém pergunte.** `offscreen` usa o mesmo motor raster do
`QPainter` que o Windows usa para widgets, então o custo de CPU da pintura é o mesmo; o que ele
não paga é a apresentação da moldura ao compositor. O número aqui é um **piso** do tempo de quadro
real — um resultado reprovado aqui seria reprovado com folga.

### 6.2 Bloqueio da thread da interface — **REPROVA**

Piso de 16 ms, 3 execuções, mediana do pior travamento. O instrumento é um `QTimer` de 4 ms na
thread da interface (o vão entre dois disparos, menos o intervalo pedido, é o tempo em que ninguém
atendeu o laço de eventos) mais um amostrador em thread separada que fotografa a pilha Python.

| | operação | pior (mediana) | excesso |
|---|---|---|---|
| **VIOLA** | abrir PDF (`load_pdf`, 1ª página a 300 DPI) | **244,2 ms** | 228,2 ms |
| **VIOLA** | virar para a página 42 (`ir_para_pagina`) | **180,6 ms** | 164,6 ms |
| **VIOLA** | virar para a página 121 | **177,8 ms** | 161,8 ms |
| **VIOLA** | virar para a página 41 | **172,8 ms** | 156,8 ms |
| **VIOLA** | rasterizar página a 300 DPI (`render_pdf_page`) | **69,8 ms** | 53,8 ms |
| **VIOLA** | aba Dataset: mostrar e carregar as amostras | **17,4 ms** | 1,4 ms |
| ok | aba Galeria: mostrar | 4,6 ms | — |
| ok | carregar índice da Galeria do livro | 0,2 ms | — |
| ok | contar páginas do PDF | 0,0 ms | — |
| ok | ajustar a página (fit-to-page + repintura) | 0,0 ms | — |

A aba Dataset entra e sai da lista entre execuções (14,1 ms numa medição anterior, 17,4 nesta):
ela carrega 5.431 amostras e fica **na fronteira** dos 16 ms. As cinco primeiras não têm essa
ambiguidade — são uma ordem de grandeza acima do piso, sempre.

A pilha do pior é inequívoca e sempre a mesma:

```
painel_do_pdf.py:472 ir_para_pagina
painel_do_pdf.py:458 _ir_para
painel_do_pdf.py:533 desenhar_pagina
pdf_io.py:186 render_pdf_page
  __init__.py:11889 get_pixmap        (PyMuPDF)
  mupdf.py:52564 fz_run_display_list
```

**§7.1 registra o conserto e por que ele não foi feito aqui.**

### 6.3 Progresso — **REPROVA (1)**

| operação | total conhecido? | determinada? | cancelável? |
|---|---|---|---|
| **detecção de duplicatas** | **sim** | **NÃO** | **NÃO** |
| treino do modelo | sim | sim | sim |
| exportação para PGN | sim | sim | sim |
| varredura da Galeria | sim | sim | sim |
| `DialogoDeTreino`: barra fixa | não | não | não |
| leitura de folha (Texto) | não | não | não |

O defeito é o par: o total está à vista no próprio texto que a operação escreve na tela —
`detail=f"{len(rotulos)} imagem(ns)"` — e mesmo assim não é passado como número. A barra anda de
um lado para o outro enquanto a frase ao lado diz exatamente quantas imagens são. **§7.2.**

---

## 7. O que foi deliberadamente adiado, e por quê

### 7.1 Rasterizar a página fora da thread da interface (D13) — **o maior débito**

**Medido:** 244 ms ao abrir, 173–181 ms por virada de página, 70 ms por rasterização isolada.
**Causa:** `PainelDoPdf.desenhar_pagina` é síncrono e chama `render_pdf_page` direto do slot.

**O conserto** é submeter a rasterização a uma `Tarefa` (`qt/trabalho.py`, que já existe e já é
usada pela detecção de caixas) e entregar `page_rgb` por sinal. **O que o impede de caber nesta
frente:** `desenhar_pagina` devolve `bool` e o produto inteiro depende de `page_rgb` estar
preenchido no retorno — **48 referências** a `desenhar_pagina`, `ir_para_pagina` e `page_rgb` fora
do próprio painel (`grep -rn ... src/ tests/`), incluindo os caminhos de OCR e a navegação da
Galeria. Tornar a chamada assíncrona é refazer esse contrato,
e fazê-lo às pressas contra uma suíte de 4.412 testes trocaria um defeito medido por um risco não
medido. **É trabalho de uma frente de desempenho, com o arnês já pronto para cobrar o resultado.**

**O que fica pronto para quem pegar:** `caissa.ui.audit.bloqueio` roda em três comandos, reporta a
mediana de três execuções e nomeia a pilha; `bloqueio.sem_travar(...)` e `@bloqueio.nao_pode_travar`
são o contexto e o decorador que transformam o portão em asserção de teste, prontos para envolver
o caminho novo.

### 7.2 Progresso determinado e cancelamento na deduplicação (D12)

O laço caro de `find_duplicate_groups` é um `for filename, fen in labels` limpo, e o conserto são
dois parâmetros opcionais — `progresso: Callable[[int], None] | None` e `cancelar: Callable[[], bool] | None`.
**Ele mora em `src/chess_diagram_ocr/audit.py`, que não é `ui/` nem `qt/`** — os dois diretórios
que esta frente pode editar. Passar `total=` ao registro sem ter como avançá-lo produziria uma
barra determinada **parada em zero**, que é pior que a indeterminada de hoje. Fica medido,
nomeado e fora da fronteira.

### 7.3 O piso da janela é 1243×890 (D14)

A janela recusa 1280×800: o mínimo é 1243×890 na pele clássica e 1243×924 na "Foco". **A causa foi
isolada:** a aba Galeria pede 732×800 de mínimo, e dentro dela `painel_da_galeria.py:268` faz
`self.recorte.setFixedSize(420, 420)` — o recorte do diagrama tem lado **fixo**. As outras abas
pedem entre 138 e 592 px de altura; sem a Galeria o piso da janela cairia para ~690 px.

**O conserto** é dar ao recorte um piso e deixá-lo crescer, reescalando o `QPixmap` no
`resizeEvent` — e atualizar `test_qt_painel_da_galeria.test_o_recorte_tem_o_lado_declarado`, que
hoje afirma o tamanho fixo. Não foi feito porque é mudança de leiaute de painel com teste próprio,
e a fila de defeitos que **reprovam sozinhos** (texto cortado, contraste, tofu, ícone) vinha
antes. Um 1366×768 é uma tela comum, e este é o item que mais atrapalha uma pessoa real.

### 7.4 Aproveitamento do espaço a 1920×1080 (D15)

O tabuleiro para em `MAX_DO_TABULEIRO = 560` px e deixa ~430 px de moldura de cada lado; a metade
inferior do painel de Resultado fica vazia. Não é defeito de correção — é espaço que um editor
profissional usaria. Exige decidir *o quê* colocar ali, que é desenho de produto e não conserto.

### 7.5 O texto do `QProgressBar` (D18)

Se alguém ligar `setTextVisible(True)`, a porcentagem cruzará o preenchimento e metade dela ficará
a ~1,5:1. O produto o mantém desligado (`qt/rodape.py:126`, verificado), então o par não existe na
tela de hoje. O conserto correto é um papel próprio para o preenchimento da barra, escolhido para
carregar o texto sobre **os dois** fundos; um token novo por um par que o produto não desenha não
se pagava agora.

### 7.6 Unificação das quatro aplicações

A frente se chama "interface unificada" e o que ela entregou foi **auditoria e qualidade da
interface que existe**. Foi escolha explícita: a carta dos críticos julga o que se vê e o que se
mede, e uma aplicação unificada pela metade perde para uma aplicação polida. O caminho para o
resto está aberto e é o mesmo que esta frente usou duas vezes: **decisão para `ui/`, desenho para
`qt/`**, com o teste de arquitetura de `tests/unit/ui/test_arquitetura.py` cobrando a fronteira a
cada execução.

---

## 8. O que foi unificado (e é o item arquitetural da frente)

### 8.1 A folha de estilo mudou de `qt/` para `ui/`

`folha_de_estilo` e o mapa da `QPalette` são a decisão de cor e de espaço da janela inteira — qual
cinza é painel, qual é botão, qual azul é foco, quanto respira cada controle. Eles moravam em
`qt/tema.py` só porque o consumidor é `QApplication`. **O preço disso era exato:** o venv da suíte
não tem binding de Qt nenhum, então o portão "contraste WCAG AA em 100 % dos pares" do §11.3 não
podia ser afirmado por teste ali — o `import` morria antes da primeira asserção.

Agora `ui/folha_de_estilo.py` devolve uma string e um dicionário de nomes; `qt/tema.py` traduz
nome de papel em `QPalette.ColorRole` em cinco linhas e reexporta o resto, de modo que os quinze
pontos de chamada e os testes já escritos não precisaram saber que a fronteira se moveu.
**Consequência direta:** 83 testes novos rodam na suíte, sem Qt, incluindo o portão de contraste.

### 8.2 A `QPalette` passou a ser aplicada — a armadilha que a frente anterior nomeou e não fechou

`_aplicar_paleta` estava **escrita e nunca chamada**. O efeito estava fotografado em
`amostrario_claro.png`: a linha selecionada da lista no azul de fábrica do Windows e a da tabela no
`SELECAO` da folha — **duas cores de "selecionado" na mesma imagem**. A causa é real e é de Qt: um
item de `QAbstractItemView` é pintado por um *delegate*, e `QStyle.drawPrimitive(PE_PanelItemViewItem)`
lê `option.palette`, não a folha de estilo.

Folha e paleta não são redundantes — são **camadas**. A folha decide o que ela alcança; a paleta é
a resposta para o que é desenhado por baixo dela. As duas leem `tokens.cor`, então não há um
segundo lugar onde a cor é escolhida; há um segundo lugar onde ela é **entregue**. Vinte papéis de
paleta nos grupos vivos e oito no grupo `Disabled`, este último grupo próprio e não um alfa — sem
ele o Qt deriva o texto morto do `WindowText` e a derivação cai em 2,6:1 contra o cromo escuro.

### 8.3 Onze papéis de relevo, e a cor do ícone

`SUPERFICIE_ELEVADA`, `AFUNDADA`, `SOBRE`, `PRESSIONADA`, `CONTORNO_DE_CROMO`, `SEPARADOR`,
`FOCO`, `SELECAO`, `TEXTO_SOBRE_SELECAO`, `TRILHO_DE_ROLAGEM`, `POLEGAR_DE_ROLAGEM` deixaram de
não existir. Antes a folha declarava duas coisas — a superfície e a letra — e deixava o resto ao
desenho nativo; sob a pele escura isso não degrada, **quebra**, porque `QWidget { background-color }`
alcança toda subclasse e botão, campo, lista e painel saíam do mesmo hexadecimal.

E `ui/folha_de_estilo.tinta_do_papel` respondeu a pergunta que estava sendo respondida em **dois**
pontos de chamada, e errada nos dois: de que cor é o ícone de um botão com ênfase.

---

## 9. Testes acrescentados

`tests/unit/ui/` — **83 testes, ~1 s, sem Qt instalado**:

| arquivo | o que ele afirma |
|---|---|
| `test_contraste.py` | o portão inteiro: nenhum par abaixo do piso nas duas peles; as quatro origens representadas; toda isenção com motivo; o rótulo do botão de ênfase sob o ponteiro; a seleção contra os dois fundos |
| `test_cascata.py` | o motor do checador: herança de classe, especificidade, estado, seletor descendente, subpeça transparente, o `max` do limite de componente, o transitório medido-mas-isento |
| `test_arquitetura.py` | **nenhum módulo de `ui/` importa toolkit** (quatro bindings de Qt, tkinter, wx, gi, kivy) e nenhum importa `chess_diagram_ocr.qt`; a folha de estilo mora em `ui/`; nenhuma isenção sobra; os cinco arneses importam sem trazer Qt junto |
| `test_medicao.py` | a aritmética dos portões numéricos: percentil por posto (não interpolado), fps do p95 e não da média, mediana como execução inteira, o vão do pulso, a cópia da lista viva, as isenções do teclado |
| `test_tema_escuro.py` | a elevação que inverte de sentido, a matiz que sobrevive, nenhum papel que seja o negativo exato, o documento que não segue a pele |

**A aritmética tem teste próprio, separado do arnês, e a razão é assimétrica.** Um portão numérico
se quebra de dois jeitos: a janela pode ficar lenta, ou a conta pode ficar generosa. O primeiro o
crítico descobre rodando o arnês; o segundo não aparece em execução nenhuma — um p95 que na
verdade interpola, um fps derivado da média, um `zip` que perde o último quadro, todos devolvem
números plausíveis para sempre.

**Dois defeitos reais foram achados pelos próprios testes**, e vale registrar:

1. `bloqueio.atrasos` fazia `zip(marcas, marcas[1:], strict=True)` sobre a **lista viva** do
   `Vigia`, que o `QTimer` faz crescer durante a leitura — `ValueError` no meio da terceira
   execução, derrubando a medição inteira. Corrigido com uma cópia, e o teste reproduz a condição
   com uma sequência que cresce enquanto é percorrida.
2. `Estatisticas.passou()` comparava `fps_p95 >= 55.0`, e `1000 / (1000 / 55)` dá
   **54,99999999999999** em ponto flutuante: uma varredura em que todo quadro custa exatamente o
   orçamento declarado reprovava por 1e-14 de fps. Passou a comparar **tempo de quadro** contra o
   orçamento — a grandeza medida, sem a divisão.

---

## 10. Antes e depois — as capturas

Todas em `benchmarks/reports/ui/`, 6 abas × 2 peles × 2 tamanhos, `antes_*` e `depois_*`.

| Aba | Antes (clara / escura) | Depois (clara / escura) |
|---|---|---|
| Resultado | `antes_claro_1280x800_resultado.png` · `antes_escuro_1280x800_resultado.png` | `depois_claro_1280x800_resultado.png` · `depois_escuro_1280x800_resultado.png` |
| Estudo | `antes_*_estudo.png` | `depois_*_estudo.png` |
| Revisão | `antes_*_revisao.png` | `depois_*_revisao.png` |
| Texto | `antes_*_texto.png` | `depois_*_texto.png` |
| Dataset | `antes_*_dataset.png` | `depois_*_dataset.png` |
| Galeria | `antes_*_galeria.png` | `depois_*_galeria.png` |
| — (1920×1080) | `antes_{claro,escuro}_1920x1080_*.png` | `depois_{claro,escuro}_1920x1080_*.png` |
| prancha de controles | — | `amostrario_claro.png` · `amostrario_escuro.png` |

**As três comparações que valem a pena abrir lado a lado:**

1. `antes_escuro_1280x800_estudo.png` × `depois_escuro_1280x800_estudo.png` — as barras de rolagem
   brancas de 12 px de cada lado da página, que eram a prova mais barata de que o tema escuro não
   era um tema.
2. `antes_escuro_1280x800_galeria.png` × `depois_escuro_1280x800_galeria.png` — o "opiar linl" e
   os dois botões com caixa vazia no lugar do símbolo.
3. `antes_escuro_1280x800_dataset.png` × `depois_escuro_1280x800_dataset.png` — o `"Conjunt"` no
   cabeçalho e o `"Bran…"` em 5.431 linhas.

---

## 11. Arquivos

**Suíte** (`Suite_de_Edicao_de_Xadrez`):

| arquivo | linhas | papel |
|---|---|---|
| `src/caissa/ui/audit/contraste.py` | 939 | o portão de contraste: analisador de QSS, cascata, derivação dos pares |
| `src/caissa/ui/audit/bloqueio.py` | 691 | o pulso, o amostrador de pilha e o contexto de asserção do §11.3 |
| `src/caissa/ui/audit/quadros.py` | 534 | o tempo de quadro do pan e do zoom |
| `src/caissa/ui/audit/teclado.py` | 506 | a volta do `Tab`, o nome acessível e o papel |
| `src/caissa/ui/audit/progresso.py` | 389 | barra indeterminada e operação sem cancelamento |
| `src/caissa/ui/audit/amostrario.py` | 210 | a prancha de controles nos estados que a tela feliz não tem |
| `src/caissa/ui/audit/capture.py` | 130 | as 24 capturas |
| `tests/unit/ui/*` | 765 | os 83 testes |

**Tronco** (`ChessVisionOFF_Puro`, `ui/` e `qt/` apenas):

| arquivo | mudança |
|---|---|
| `ui/folha_de_estilo.py` | **novo** (547) — a folha, o recheio, o mapa da paleta e `tinta_do_papel`, sem toolkit |
| `ui/nomes_acessiveis.py` | **novo** (82) — a cascata que decide como um controle sem rótulo é anunciado |
| `qt/acessibilidade.py` | **novo** (117) — a varredura que executa essa cascata |
| `ui/tokens.py` | +125 — os onze papéis de relevo, `afastar`, e os valores re-derivados de `SELECAO`, `CONTORNO_DE_CROMO` e `TEXTO_SOBRE_SELECAO` |
| `qt/tema.py` | −228/+... — a folha saiu; `aplicar_paleta` virou pública **e passou a ser chamada** |
| `qt/tabuleiro.py` | +63 — o glifo de reserva com contorno |
| `qt/painel_da_galeria.py` | +38 — a fileira de "Este diagrama" fluida |
| `qt/tabela.py` | +34 — a seção nunca menor que o título medido |
| `ui/strings.py` | +33 — os glifos de navegação, o estado vazio do editor, o nome do painel de detalhes |
| `ui/estilos.py` | +23 — `COM_ENFASE` e `tem_enfase` |
| `qt/fita.py`, `qt/fila.py` | +16 — o ícone pergunta a cor em vez de decidi-la |
| `ui/resumo_do_dataset.py` | +12 — as larguras de coluna re-medidas |
| `qt/painel_de_texto.py`, `qt/painel_de_resultado.py`, `qt/janela.py` | +11 — estado vazio, nome do painel de detalhes, a varredura de nomes |
| `tests/test_editor_model.py`, `tests/test_ui_estilos.py`, `tests/test_ui_tokens.py` | +20 — os dois módulos novos registrados, a isenção de estilo transferida junto com o código, e a coincidência de `TEXTO_SOBRE_ENFASE`/`TEXTO_SOBRE_SELECAO` declarada com o motivo |
