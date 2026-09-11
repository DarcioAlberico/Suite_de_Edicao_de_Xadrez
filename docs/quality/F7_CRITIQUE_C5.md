# F7 — Crítica adversarial, ciclo 5

```
VEREDITO: REPROVADO
CICLO: 5
FRENTE: F7 (Tipografia)
```

> **Nota de procedimento — desta vez o teste cego foi cego.** A Fase 1 inteira foi medida,
> escrita e gravada em `benchmarks/reports/critique/c5/phase1.md` **antes** de eu abrir
> `GABARITO.json` e **antes** de abrir qualquer documento de histórico. O único documento
> que li antes da Fase 1 foi `docs/quality/CRITIC_CHARTER.md`. A tabela abaixo é a que está
> naquele ficheiro, sem uma vírgula alterada. A correção que o ciclo 3 pediu — uma
> página-fonte inédita — foi feita: `book_source_rios` não aparece em nenhuma crítica
> anterior, e eu identifiquei a nossa amostra **por defeito medido**, não por reconhecimento
> de texto.
>
> Todas as medidas são minhas, por scripts em `benchmarks/reports/critique/c5/`.

---

## Comparação às cegas

*(preenchido ANTES de saber qual é a nossa — cópia literal de `critique/c5/phase1.md` §1)*

| Amostra | Posição | Justificativa |
|---|---|---|
| **A** | **1º** | A página mais completa e mais controlada: quatro níveis de hierarquia que se leem à primeira vista, dois diagramas **corretos** e com coordenadas, um só conjunto de figurinos, meia-risca correta no roque, itálico semântico. O único defeito real é uma política (sem hifenização ⇒ linhas frouxas). Nada nela é erro. |
| **D** | **2º** | Mesma classe, matéria mais densa, sem tropeço; diagramas verificados lance a lance contra o texto. Perde para A por 6 linhas frouxas (contra 3), por diagramas sem coordenadas e por um diagrama de baixo que pára a 66 px do corte. |
| **F** | **3º** | Mecanicamente a página mais bem composta do conjunto — a justificação, o pé de coluna e o ritmo dos diagramas batem todas as referências — mas carrega cinco faltas que nenhuma página publicada aqui comete, entre elas uma cabeça corrente sem acentos e um diagrama que contradiz os lances impressos debaixo dele. |
| **C** | **4º** | A grade mais disciplinada que medi (100 % das linhas na grade nas duas colunas, 98 % de registo transversal, pés a 0 px) e nenhum erro encontrado — mas uma justificação de 35 caracteres que força 3:1 de espaço entre palavras, e um muro indiferenciado de notação sem diagrama, sem régua, sem alívio. |
| **B** | **5º** | Hierarquia de abertura de capítulo limpa e entrelinha de 30,5 px uniforme, desfeitas por uma justificação de 74 caracteres, uma palavra partida ao meio por um espaço solto (`This endgame i s always`) e o maior salto de espaçamento entre linhas vizinhas da página. E é a que menos mostra: nenhum diagrama. |
| **E** | **6º** | Os seus dois diagramas são os objetos mais bem desenhados de qualquer das seis páginas, e as colunas fecham exatamente. O resto é frouxo: uma bandeira à direita cuja linha mediana fica 8–17 % curta e a mais funda 45 % curta, um buraco branco de 2,9 entrelinhas entre cada tabuleiro e a sua própria legenda, e a página mais vazia do conjunto (90,4 % branco). |

**Identidade revelada: a nossa era a amostra F, classificada em 3º lugar de 6.**

| Amostra | Origem (GABARITO) | Minha posição | Meu palpite real × gerado |
|---|---|---|---|
| A | referência — Quality Chess p149 | 1º | real, e a única **digitalização** ✔ |
| B | referência — Nunn p50 | 5º | real, PDF vetorial ✔ |
| C | referência — Gambit p116 | 4º | real ✔ |
| D | referência — Everyman/Aagaard p215 | 2º | real, texto vetorial + **diagramas em bitmap** ✔ |
| E | referência — Dvoretsky 2025 p215 | 6º | real, **PDF digital nativo** ✔ |
| **F** | **nossa — composta, fonte `rios`** | **3º de 6** | **gerada ✔** |

### A assimetria, medida em vez de suposta

O enunciado avisa que a nossa é vetorial e as referências são digitalizações. **Testei, e é
falso para quatro das cinco.** Dois testes independentes (`hatch2.py`, `glyph3.py`):

| | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| pares de glifos grandes idênticos ao pixel | **10 de 753 (1,3 %)** | 1698 (52 %) | 416 (24 %) | 1169 (66 %) | 3376 (75 %) | 2943 (68 %) |
| menor \|Δ\| entre casas escuras vazias | 12,40 | — | — | 7,07 | **0,000** | 0,245 |

**Só a amostra A é uma digitalização.** B, C, D, E e F são rasterizações de PDF. A
limpeza vetorial não compra nada neste conjunto. Descontei explicitamente o dano de
scanner só em A (tinta irregular, arestas esfarrapadas, oscilação de 1–2 px na linha de
base) e não o contei contra ela em lugar nenhum — e A ficou em 1º.

**Quanto isso moveu a ordenação: nada, e no sentido contrário ao previsto.** Também tive de
**retirar** uma acusação que fiz a E na primeira passagem (entrelinha variável com o
conteúdo, 52/53 contra 58/59 px): re-medida com um estimador de linha de base por gradiente
máximo, a entrelinha de E é uniforme a 52,5 px e os desvios eram erro do meu detetor. Está
registado como retratação em `phase1.md` §3 E(r).

### As grandezas que decidiram a ordem

| métrica | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| **faixa de espaço entre palavras** (máx ÷ mín da mediana por linha) | 2,86 / 3,85 | 2,33 | 3,00 / 2,58 | 3,00 / 2,86 | 4,00 / 3,83 | **1,55 / 1,73** |
| linhas acima de 1,6× a mediana da coluna | 3 | 1 | 1 | **6** | 2 | **0** |
| aderência à grade de linha de base | 70 / 83 % | 97 % | **100 / 100 %** | 28 / 100 % | 26 / 35 % | 93 / 80 % |
| registo transversal (≤1 px) | **7 %** | — | **98 %** | 62 % | 61 % | 40 % |
| desnível do pé de coluna | 39 px | — | **0** | 14 px | **0** | **0** |
| hifenizações em fim de linha | **0 %** | 14,3 % | 7,4 % | **0 %** | 2,2 % | 6,7 % |
| conjunto de figurinos | um, contorno | um | um, cheio | um, contorno | um, contorno | **misturado** |
| **linhas curtas no meio de parágrafo (< 0,94 da medida)** | **0 de 37** | **0 de 34** | **0 de 80** | **0 de 53** | (bandeira) | **9 de 29** |
| diagrama confere com o próprio texto | ✔ verificado | — | — | ✔ verificado | — | **✘** |

**O que a denunciou** (`phase1.md` §4, escrito antes da revelação): a única página não
inglesa; a cabeça corrente com os diacríticos removidos (`Capitulo`, `peoes`) enquanto o
título uma linha abaixo os mantém; um conjunto de figurinos misturado por **tipo de peça** e
não por cor nem por estilo de casa; uma quebra de linha no meio de uma frase deixando uma
linha a 54 % da medida; e um diagrama que contradiz a sequência de lances impressa debaixo
dele, quando os quatro diagramas de A e D que verifiquei lance a lance estão exatos.

---

## Adjudicação dos dois instrumentos que o construtor contestou

O construtor tem razão num e exagera no outro. Digo os dois com o mesmo peso.

### `dark2.py` — **QUEBRADO. O construtor tem razão, e o achado do ciclo 3 fica retirado.**

`critique/c3/dark2.py` amostra a moldura numa linha fixa, `y = y0 − 0,3 pt` com `y0 = 54,8`,
e toma como "cor da moldura" o pixel mais escuro (ou o mais afastado do fundo) dessa
varredura. Medi, sem usar o script (`critique/c5/frame_cr.py`), onde está de facto a
moldura nas três páginas de livro entregues:

| página | primeira tinta não-fundo | linhas da moldura | cor da moldura | **contraste contra o fundo** |
|---|---|---|---|---|
| p10 hachurada | y = 55,08 pt | 55,44–56,16 | (0, 0, 0) | **21,00 : 1** |
| p11 cinza/livro | y = 55,08 pt | 55,44–56,16 | (0, 0, 0) | **21,00 : 1** |
| p12 escura | y = 55,08 pt | 55,44–56,16 | (237, 237, 234) | **14,13 : 1** |

`dark2.py` amostra **y = 54,36 pt** — 0,72 pt acima do topo do quadro — e portanto lê fundo
de papel puro nas três páginas, imprimindo «frame = ground, CR 1,00» inclusive na página
hachurada, cuja moldura é preto puro sobre branco. **Um instrumento que reporta 1,00 : 1
numa régua preta sobre branco está quebrado**, e o método (pixel mais escuro de uma
varredura fixa) era frágil por construção, não só por deslocamento. O defeito não
bloqueante nº 10 do ciclo 3 — «moldura invisível no tema escuro, 1,14 : 1» — **fica
retirado**: 14,13 : 1 passa WCAG 1.4.11 com folga de quase 5×. Os números do construtor
(21,00 / 21,00 / 14,13) reproduzem exatamente os meus.

### `register.py` — **não está quebrado; o enquadramento do construtor exagera. Mas a conclusão dele está certa.**

`critique/c3/register.py` não «deixou de medir o que media». É um script do conjunto cego,
com `CASES` codificadas para `blind2/amostra_{B,C,D,F}.png`; nunca teve entrada para a nossa
folha porque nunca foi apontado a ela. Chamar isso de instrumento avariado é generoso para
consigo. O algoritmo é bom: ajusta a grade da coluna esquerda e testa a direita contra ela.

Apontei-o eu à nossa folha (`critique/c5/register5.py`, sobre o PDF entregue):

```
p10  coluna esquerda: 22 linhas de base, grade 10,4060 pt, resíduo máximo 0,0005 pt
     coluna direita : 15 linhas de base contra a grade da ESQUERDA
                      fase mediana 0,0001 pt, máxima 0,0003 pt, dentro de 0,4 pt: 100 %
p11, p12: idênticos
```

**Confirmado: 100 % de registo transversal com erro máximo de 0,0003 pt.** A alegação do
construtor (0,0008 pt) é honesta; a minha medida é ainda melhor. E a divergência aparente
com o «9 de 15 = 60 %» que a própria ferramenta dele imprime é real e explicável — 60 % é a
fração de linhas da direita que coincidem com uma linha **existente** à esquerda, e as
outras enfrentam um diagrama — mas o relatório põe o «100 %» em §5.2 imediatamente por baixo
do «60 %» da sua própria saída sem a linha de reconciliação. É um descuido de redação, não
de medição.

---

## Os cinco portões, re-medidos por mim

Nenhum número abaixo veio do relatório sem eu o reproduzir, e onde a ferramenta é do
construtor eu digo isso e acrescento uma medida independente.

| # | Alegação do ciclo 4 | A minha verificação | Veredito |
|---|---|---|---|
| Q1 | 70/22 hastes, 0 contornos partidos; 93,5 % / 83,0 % de tinta sobrevive; ponta a 3,39:1 / 3,34:1 | Ferramenta reproduz exatamente. **Olhei** o espécime da p5 a 600 DPI (`pf05_marks.png`): as três hastes passam **por baixo** do cavalo de d2, do peão de c5, do peão de d5 e do bispo de g2, com os contornos inteiros — é uma correção real e visível. Medida independente no raster do tema escuro entregue: ponta `(214,96,77)` contra tinta de peça preta `(20,23,26)` = **4,97 : 1** | **FECHADO** |
| Q2 | 16 rótulos inteiros, 0 peças com entalhe | Ferramenta reproduz. **Olhei** o espécime da p4 a 600 DPI: nenhum entalhe, nenhuma letra cortada, o `g` desviou-se do rei. **Mas** — ver defeito não bloqueante nº 3 — o desvio partiu a fila: sete rótulos de coluna assentam em `y = 199,71 pt` e o `g` em `y = 187,57 pt`, **12,14 pt acima**, dois terços de uma casa | **FECHADO à letra, com uma falta nova** |
| Q3 | 222 tokens, 3 legendas, cabeça corrente, 93 negrito + 15 itálico, 0 divergências não declaradas | `compare_exporters.py` reproduz **exatamente**, dígito a dígito, exit 0. Verifiquei também que os itens do ciclo 3 estão fechados: `After 21.♗xh7†.` igual nos dois, travessão igual, espaço depois da reticência 0,00/0,00 pt. **Mas o instrumento é cego à identidade das peças** — ver bloqueante nº 2 | **NÚMEROS CONFIRMADOS; O INSTRUMENTO NÃO MEDE O QUE O Q5 ALEGA** |
| Q4 | teto de vão, vãos rígidos de título, recuo, teto de espaço entre palavras | `holes` 3,47 el (espécime, teto 4) e 1,91 el (livro, teto 2); `indent` 0 blocos; `wordspace` 1,73× máximo e 0 linhas acima de 2,0×; `feet` 0,000 mm nas três páginas de livro; `bottom` 12/12 dentro da margem, transbordo 0,00 mm. Todos reproduzem. **Mas o 1,73× é comprado com o bloqueante nº 1**, e o teto de vão não impede que elementos equivalentes levem espaços diferentes (não bloqueante nº 1) | **CRITÉRIOS CUMPRIDOS; A INTENÇÃO NÃO** |
| Q5 | fechado na paridade entre exportadores; grade e símbolos de avaliação declarados abertos | Registo transversal **confirmado a 100 %, 0,0003 pt** — e **empata** com a amostra C deste conjunto (98 % medido a 200 DPI num render vetorial). A paridade, que é onde o Q5 assenta, **é demonstravelmente cega ao símbolo de peça** — bloqueante nº 2 | **NÃO FECHADO** |
| — | 2912 passam / 1 pula | `pytest tests/unit/typeset -q -p no:randomly`: **263 passed, 1 skipped em 250,34 s**, o único skip é o do Brotli. Bate com o relatório (263/1 em 220,63 s). Não corri a suíte completa de 10 minutos três vezes | **CONFIRMADO no subconjunto** |
| — | (não alegado) reprodutibilidade | Regerei a folha **três vezes** para diretórios de rascunho: as três camadas de texto são idênticas entre si **e idênticas à do artefato entregue**, 1507 spans em cada. O que está no disco é o que o código produz | **CONFIRMADO — e conta a favor** |

---

## Defeitos bloqueantes

### 1. O compositor desiste da justificação no meio do parágrafo e deixa até 45 % da medida em branco — e é assim que o 1,73× do Q4 nº 5 foi comprado.

**Onde:** `tools/typeset_page.py::break_paragraph`, o ramo que devolve
`SetLine(..., justify=False)`. Visível em `benchmarks/reports/proofsheet.pdf` p10/p11/p12 e
em `benchmarks/reports/blind3/amostra_F.png`.

**O que:** quando o otimizador não consegue uma linha dentro de `MAX_SPACE_RATIO = 2.0` e a
hifenização não a salva, a linha é composta **rente à esquerda no espaço nominal**. A
docstring justifica-o assim: *«A short right edge is a smaller fault than a river, and it is
what a compositor does»*. Um compositor não deixa 45 % de uma linha em branco no meio de um
parágrafo justificado; o que ele faz é re-quebrar, hifenizar, ou aceitar uma linha um pouco
acima da tolerância. Uma linha a 55 % da medida seguida de uma linha cheia **lê-se como fim
de parágrafo** — destrói a estrutura do texto, não só o seu aspeto.

**Como reproduzir:** `.venv\Scripts\python.exe benchmarks\reports\critique\c5\unjustified2.py`

```
mareco / proofsheet p10-12   37 linhas de corpo; 5 com a justificação abandonada a meio
   fill 0,70  (44,1 de 63,5 mm)  |Better was: 13…[N]xc5 14.[N]b3 [N]e6|
   fill 0,75  (47,4 de 63,5 mm)  |Black lost this game in one move, with|
   fill 0,83 · 0,84 · 0,91
rios / blind3 amostra_F      42 linhas de corpo; 4 com a justificação abandonada a meio
   fill 0,55  (34,7 de 63,5 mm)  |página: 13…[N]xc5 deixa um|
   fill 0,80  (51,0 de 63,5 mm)  |casas centrais e prometem a ruptura …d4.|
   fill 0,83 · 0,89
```

**Nas referências** (`critique/c5/midshort.py`, verificado linha a linha nos casos que o
detetor sinalizou): **A 0, B 0, C 0, D 0.** As seis linhas que o detetor marcou em D são
falsos positivos — são linhas finais de parágrafo seguidas de uma linha de lances em
negrito rente à margem, e confirmei-o ampliando `D_y410.png`. Nenhuma das quatro páginas
justificadas do conjunto tem uma única linha de meio de parágrafo abaixo de 0,94 da medida.

**Por que reprova:** carta §3.3 — *«Espaçamento de parágrafo que muda sem razão semântica»*
e *«Espaçamento inconsistente entre elementos equivalentes»*. E porque é a **conta que falta
no Q4 nº 5**: a única vantagem clara que a Fase 1 mediu a nosso favor — a faixa de espaço
entre palavras mais apertada do conjunto, 1,55–1,73 : 1 contra 2,33 : 1 da melhor referência
— existe porque **1 linha em 8 é retirada da conta**. A ferramenta `wordspace` mede as
linhas que o compositor justificou e não conta as que ele recusou justificar. A métrica
melhorou enquanto a página piorava, que é exatamente o padrão que o ciclo 3 nomeou para as
contrapunções do figurino em negrito.

### 2. O portão em que o Q5 assenta é cego à identidade das peças. Provado por sabotagem.

**Onde:** `tools/compare_exporters.py`. O Q5 do ciclo 3 pedia *«o mesmo livro nos dois
exportadores, indistinguível token a token e span a span»* e o relatório do ciclo 4 diz
explicitamente: *«É a única das três candidatas que este ciclo ganha, e é sobre ela que
assento o Q5.»*

**O que:** o script normaliza os figurinos para fora, nos **dois** lados. A docstring dele
di-lo: *«Spans set in the chess font are replaced by a single space»*. Um símbolo de peça
errado é portanto invisível.

**Como reproduzir:**

```
copiei benchmarks\reports\latex\livro.tex para um diretório de rascunho
troquei UM \cfig{knight} por \cfig{queen} no primeiro lance do livro
pdflatex duas passagens, exit 0
.venv\Scripts\python.exe tools\compare_exporters.py --tex <o PDF sabotado>
```

```
--- pagina inteira, token a token
    222 tokens, identicos.
--- estrutura: quais corridas saem em negrito     93 negrito, identicos.
--- estrutura: quais corridas saem em italico     15 italico, identicos.
TOTAL: 0 divergencia(s) nao declarada(s) + 1 declarada
EXIT=0
```

A página do LaTeX agora imprime **`1.d4 ♕f6`** — uma dama onde estava o cavalo, no primeiro
lance do livro, um lance impossível — e o portão diz que os dois exportadores são idênticos.
Recorte a 400 DPI: `critique/c5` (o comando está acima; a imagem é reproduzível em segundos).

**Por que reprova:** o construtor descobriu sozinho que *«nenhuma comparação de tokens pode
ver uma caixa»* e corrigiu o `showmover`. A conclusão que tirou foi «rode o script **e**
olhe as duas páginas». A conclusão certa era que o mesmo buraco engole os símbolos de peça,
que não são mobília — são o conteúdo primário de um livro de xadrez e cerca de 15 % dos
tokens da página. Uma medida de paridade que não vê a diferença entre um cavalo e uma dama
**não pode sustentar a única vantagem alegada do ciclo**. Carta §5.1: empate não aprova, e
uma vantagem medida por um instrumento cego ao que interessa é menos que um empate.

### 3. O figurino em linha não vem de um só conjunto: dama e rei saem cheios, torre/bispo/cavalo/peão saem em contorno, independentemente de quem joga.

**Onde:** a página de livro entregue, `proofsheet.pdf` p10/p11/p12, e a amostra cega F.

**O que:** na mesma corrida em negrito da página entregue —
`Better was: 13…♘xc5 14.♘b3 ♘e6 15.♕d2 ♕f6 16.e3±` — os **três cavalos** são desenhados com
o glifo **oco** (peça branca) e as **duas damas** com o glifo **cheio** (peça preta). Os
lances alternam de cor: `13...♘xc5` é das pretas, `14.♘b3` é das brancas, `15.♕d2` é das
brancas, `15...♕f6` é das pretas. Não é «contorno para as brancas, cheio para as pretas», e
não é «um só conjunto». Medido a 1200 DPI (`critique/c5/figink2.py`): cavalos com fração de
tinta **0,31–0,40** da sua caixa, damas com **0,60**.

O mesmo na amostra cega: `14.♘b3! ♕c7 15.♕d2 ♖fd8 16.♖fd1` — duas damas cheias entre
cavalo e torres ocas, com `♕c7` das pretas e `♕d2` das brancas ambas cheias, e `♖fd8` das
pretas e `♖fd1` das brancas ambas ocas.

**Que não é desenho da fonte:** no **diagrama** da mesma página a dama branca de d1 é oca e a
dama preta de d8 é cheia — merida distingue as cores corretamente. É o caminho do figurino
em linha que escolhe o glifo errado.

**Nas referências:** A e D usam um conjunto oco para os dois lados; C usa um conjunto cheio
para os dois lados; B e E usam um conjunto só. **Nenhuma das cinco mistura.**

**Por que reprova:** carta §3.3 — *«Ícones de origens diferentes misturados (peso, estilo,
grade)»*. É visível à distância de leitura: a dama cheia mancha a linha ao lado de um cavalo
oco do mesmo corpo, e o leitor não pode usar o preenchimento para ler o lado, como pode nos
diagramas da mesma página.

### 4. Nenhum dos dois exportadores produz uma camada de texto utilizável para notação de xadrez, e um deles produz uma camada de texto **enganosa**.

**Onde:** `proofsheet.pdf` p10 e `latex/livro.pdf` p1.

**O que:** extraindo o texto dos dois PDF entregues:

| | linha de lances extraída | busca por `Nf6` | por `Nb3` | por `Qxh7` |
|---|---|---|---|---|
| SVG→PDF | `14…c4 runs into 15. d4, and 14… c8 15. c2` | 0 | 0 | 0 |
| LaTeX | `1.d4 †f6 2.c4 e6 3.g3 …b4† 4.…d2 …xd2†` | 0 | 0 | 0 |

O lado SVG desenha o figurino como traçado vetorial e **não deixa texto nenhum**: quem copia
uma linha do livro obtém notação mutilada. O lado LaTeX emite um glifo de `Chess-Alpha` cujo
`ToUnicode` mapeia o cavalo para **`†`**, o bispo para **`…`** e a dama para **`ƒ`** — e `†` é
o símbolo de xeque **deste mesmo livro** e `…` é a reticência de lance das pretas **deste
mesmo livro**. `4.…d2 …xd2†` lê-se como «4. ...d2 ...xd2+»: não é perda, é erro.

Consequências para um editor profissional: copiar e colar dá lixo; a busca de texto no PDF
não encontra um único lance; um leitor de ecrã lê `1.d4 f6`. E é isto que obriga
`compare_exporters.py` a normalizar os figurinos para fora — o bloqueante nº 2 é o sintoma,
este é a causa.

**Por que reprova:** um livro de xadrez cujo PDF não pode ser pesquisado por um lance não é
um livro de xadrez exportado; é uma imagem de um. A auditoria de texto do ciclo 3
(«zero reticências de três pontos») passa numa camada em que a reticência que existe é um
bispo.

### 5. Nenhuma vantagem clara e mensurável sobrevive à verificação. (Carta §5.1 e condição explícita do ciclo 1.)

| Candidata | Nossa | Melhor referência | Veredito |
|---|---|---|---|
| Faixa de espaço entre palavras | **1,55–1,73 : 1**, 0 linhas acima de 1,6× | B 2,33 : 1 | **comprada com o bloqueante nº 1** — 9 linhas em 71 são retiradas da conta |
| Paridade entre exportadores | 222 tokens, 0 divergências | nenhuma editora tem dois caminhos | **medida por um instrumento cego ao símbolo de peça** (bloqueante nº 2) |
| Registo transversal | 100 %, 0,0003 pt | **C: 98 %**, e C faz 100 % de ocupação de grade | **empate, e C ganha na ocupação** |
| Pé de coluna | 0,000 mm | C 0 px, E 0 px | **empate com duas** |
| Diagramas do mesmo tamanho na página | 607/606/607 px | E 536/536 px, D 361/362 px | **empate** |
| Ocupação da grade | 43 % / 43 % (63 %/79 % descontando diagramas) | C 100 % | **perdemos** |

O construtor declara honestamente que duas das três candidaturas do Q5 continuam abertas. A
terceira, em que assentou o portão, cai por medição. Fica **zero**.

---

## Defeitos não bloqueantes

1. **Elementos equivalentes com espaços diferentes na mesma página entregue.** `move → body`
   ocorre cinco vezes em p10: **2,00 casas de linha** quatro vezes (coluna esquerda) e
   **1,00 casa** uma vez (coluna direita, y = 289,38 — `21.♗xh7†!+−` colado a `Checkmate
   cannot be avoided.`). Metade do espaço, para o mesmo par de tipos de bloco.
   `critique/c5/gapaudit.py`. O Q4 nº 1 pôs um **teto** no vão; não pôs uma regra de
   igualdade, e a justificação vertical continua a comprar o pé com vãos desiguais — só que
   agora com vãos menores.
2. **Um título órfão do que titula.** `critique/c5/orphanheads.py`: o título `2. Molduras`
   está a `y = 553,2` da p2 com **zero** dos seus seis espécimes de moldura nessa página; os
   seis estão todos na p3, que abre com eles e sem título. O Q4 nº 2 («título e primeiro
   parágrafo indivisíveis») está cumprido à letra — o parágrafo acompanha o título — e a
   intenção não. É o mesmo achado que o construtor fez sozinho para a série de 9/10/11/12 pt
   (§4.1 do relatório), na secção ao lado, e não está na lista de itens abertos.
3. **O desvio do rótulo `inside` parte a fila das colunas.** Medido no PDF
   (`critique/c5/inside_labels.py`): `a b c d e f h` assentam todos em `y = 199,71 pt`; o
   `g`, desviado para o canto livre por causa do rei, assenta em `y = 187,57 pt` —
   **12,14 pt acima**, dois terços de uma casa. Os oito rótulos de fileira, pelo contrário,
   alinham a `x = 42,04` com desvio **0,00**. Carta §3.3: *«Alinhamento óptico errado.»*
   A ferramenta `inside` conta os rótulos e não olha para onde ficaram.
4. **A cabeça corrente da amostra cega está escrita sem acentos.** `tools/build_blind.py:141`
   codifica `"rios": (ps.book_source_rios, "pt", "Capitulo 4 - peoes pendentes")`. A
   página-fonte em `typeset_proofsheet.py::book_source_rios` está **corretamente acentuada**
   (`A estrutura de peões pendentes`, `Capítulo 4 — os planos das brancas`), de modo que a
   falta está no arnês do crítico e não no compositor. Isso atenua a origem e **não** atenua
   o efeito: a página submetida a julgamento contra cinco livros publicados leva
   `peoes`, que não é uma palavra portuguesa, na cabeça corrente. E o
   `textaudit.py` — que verifica aspas retas, reticências de três pontos, espaços duplos —
   **não tem nenhuma verificação de diacríticos**, pelo que nada no projeto podia apanhar
   isto. O ficheiro inteiro do arnês está escrito em português sem acentos (`apos 13.dxc5`,
   `nao cabe numa pagina`, `posicao inicial`): uma dessas cadeias escapou para a página.
5. **Traço diferente para a mesma construção**, na mesma amostra: a cabeça corrente usa
   meia-risca (20 px de largura medidos) e o subtítulo usa travessão (37 px) para o mesmo
   `Capítulo 4 —/– …`.
6. **Três estilos de separação de parágrafo na mesma página** (amostra F): recuo só; linha em
   branco mais recuo; e nenhum dos dois — `A questão é sempre a mesma:` começa rente à
   margem na linha a seguir a uma linha a 62 % da medida. Os dois últimos são consequência do
   bloqueante nº 1; o efeito no leitor é que não se sabe onde acaba um parágrafo.
7. **O conteúdo de xadrez de `book_source_rios` está errado em três pontos.** É autoria e não
   composição, mas a página foi produzida para ser julgada:
   * o diagrama de `FEN_RIOS21` mostra um **bispo branco em h7** (fração de tinta 0,168,
     contra 0,153 de um bispo branco conhecido e 0,273 de uma peça preta) e a linha impressa
     logo abaixo é `21.♗xh7†! ♔xh7 22.♕h5† ♔g8 23.♖g3` — o rei preto capturou esse bispo no
     lance 21, e a dama em h5 com a torre em g3 fixam o diagrama no lance 23 ou depois;
   * `16…d4 17.♘xc5 dxc3` — **c3 está vazia** e as brancas não têm peão na coluna c;
   * `16…♘e5 17.♘xc5 ♗xc5` — o **único bispo preto está em b7**, casa clara; c5 é escura.

   Verifiquei os dois diagramas de A lance a lance contra a partida impressa (Polgar –
   Dominguez, 17.exd5: as 26 peças conferem) e os dois de D contra `4...♔f6!`. Ambos exatos.
8. **Fragmentação.** 56 % / 60 % das linhas da amostra F são finais de parágrafo — parágrafo
   médio de ~2 linhas, contra 37/34 % em A, 41/18 % em D e 7/2 % em C. A página lê-se como
   apontamentos e não como prosa. É escolha do texto-fonte, não do compositor, mas é a
   página que nos representa.

---

## O que verifiquei e está sólido

Por dever de §5.5, e porque é muito.

* **O Q1 está fechado de verdade, e eu olhei.** A 600 DPI, no espécime da p5, as três hastes
  passam por baixo das peças com o contorno inteiro e as pontas trazem o contorno claro que
  as separa da peça de destino. Era, no ciclo 3, cabeças de peão decapitadas e uma base de
  peão substituída pela ponta da seta. Independentemente da ferramenta, medi a ponta do tema
  escuro contra a tinta da peça preta: **4,97 : 1**.
* **O Q2 está fechado quanto ao que pedia:** 16 rótulos inteiros, nenhum cortado pela aresta,
  zero entalhes nas peças, e a casa cheia devolve as coordenadas para fora.
* **Os números do Q3 reproduzem dígito a dígito**, e as cinco divergências que o ciclo 3
  mediu estão todas fechadas — incluindo os 5,12 pt depois da reticência e os 71-contra-7
  spans em negrito, que agora são 93 contra 93.
* **O `showmover` foi encontrado a olho, e é o achado certo.** O construtor descobriu que o
  `chessboard` imprimia um quadrado de «quem joga» que o SVG não imprimia, que nenhuma
  comparação de tokens podia ver, e corrigiu-o. Foi por olhar, não por medir. É exatamente
  o método que a carta §3.1 exige, e funcionou.
* **A série de 9/10/11/12 pt partida entre p6 e p7 foi encontrada da mesma maneira**, e o
  construtor declarou que o teste correspondente só procurava rótulos terminados em `mm`.
  Admitir que o próprio teste era estreito é raro e conta.
* **O construtor tinha razão sobre `dark2.py`.** Um construtor que verifica o instrumento do
  crítico em vez de argumentar contra o número está a fazer a coisa certa, e neste caso o
  instrumento estava mesmo avariado. Retirei o achado.
* **Reprodutibilidade exata, três execuções.** Regerei a folha três vezes: 1507 spans, camada
  de texto **idêntica** entre si e idêntica à do artefato entregue.
* **A suíte roda:** `tests/unit/typeset` → 263 passed, 1 skipped (Brotli) em 250 s.
* **O pé de página é real:** 12/12 páginas dentro da margem, transbordo 0,00 mm; pés das três
  páginas de livro a 0,000 mm de diferença.
* **A grade é rígida:** 10,4060 pt com resíduo máximo de 0,0005 pt sobre 22 linhas, e 100 %
  de registo transversal a 0,0003 pt. É melhor que qualquer referência que medi na fase 1
  em precisão, ainda que empate em cobertura.
* **A justificação, olhada só nas linhas que ele justifica, é a melhor do conjunto** —
  1,55–1,73 : 1 contra 2,33 a 4,00 : 1. O otimizador de Knuth–Plass é a coisa certa a ter
  feito. O problema é o ramo de desistência, não o otimizador.
* **Os cinco itens menores do ciclo 3 estão fechados e re-medidos:** menor corpo da folha
  5,61 pt (era 3,40), legenda `90 mm` a 0,34 mm do tabuleiro (era 9,3 mm), `+−` com U+2212,
  continuações de sub-variante recuadas (0 blocos), secções numeradas 1–9 únicas,
  `After 14.♘b3` com figurino em vez de `N` de ASCII, moldura do tema escuro a 14,13 : 1.
* **A folha subiu de 4º de 6 para 3º de 6 contra um conjunto mais forte** (quatro das cinco
  referências são renders vetoriais, não digitalizações), e desta vez o teste cego foi cego.

---

## O que especificamente precisa mudar para eu aprovar

Quatro itens. Cada um com número verificável. Nada mais.

**R1 — Uma linha de meio de parágrafo tem de chegar à medida.**
Substituir o ramo `justify=False` por uma das saídas que um compositor usa: (a) permitir que
a hifenização quebre também dentro de uma corrida de notação longa (`13...Nxc5` é o token
que estoura a linha nos cinco casos que medi); (b) deixar `max_space_ratio` subir para 2,2×
numa linha em vez de a abandonar; (c) re-quebrar o parágrafo com penalização finita para a
linha larga em vez de penalização de 10⁶ para o transbordo.
Critério, nas três páginas de livro **e** numa página composta a partir de
`book_source_rios`: **zero** linhas de meio de parágrafo abaixo de **0,94** da medida.
Hoje: 5 de 37 e 4 de 42, a pior a **0,55**. Referências A, B, C, D: **0**.
Reportar, junto com o `wordspace`, **quantas linhas o compositor recusou justificar** — uma
métrica de espaço entre palavras que não conta as recusas não é uma métrica.

**R2 — A paridade tem de comparar as peças.**
`compare_exporters.py` normaliza os figurinos para fora dos dois lados. Tem de os comparar:
do lado LaTeX a partir do argumento de `\cfig{...}` no `.tex` gerado, do lado SVG a partir
do `Run.kind == "piece"` da lista de corridas — as duas fontes de verdade já existem e já
saem da mesma passagem de marcação.
Critério: com **um** `\cfig{knight}` trocado por `\cfig{queen}` no `.tex`, o script tem de
sair com pelo menos **1 divergência não declarada** e nomear o token. Hoje sai com
`222 tokens, identicos` e exit 0. Repetir a sabotagem para cada uma das seis peças.

**R3 — Um só conjunto de figurinos na notação em linha.**
A dama e o rei estão a sair com o glifo da peça preta e a torre, o bispo, o cavalo e o peão
com o da peça branca, independentemente de quem joga, enquanto o diagrama da mesma página
usa o preenchimento corretamente para distinguir os lados.
Critério: para as seis peças, a fração de tinta do glifo em linha tem de cair na mesma banda
(±0,08) que a do mesmo glifo desenhado no diagrama para a **mesma cor**. Hoje: cavalo 0,31–0,40,
dama 0,60, no mesmo lance em negrito. Teste novo, e olhar a linha
`13…♘xc5 14.♘b3 ♘e6 15.♕d2 ♕f6` a 600 DPI.

**R4 — Uma camada de texto que se possa pesquisar.**
Os dois exportadores têm de emitir a notação como texto legível: do lado SVG, um span de
texto invisível (`render_mode 3`) com a letra da peça por baixo do traçado; do lado LaTeX,
um `ToUnicode` correto para `Chess-Alpha` em vez de `†`, `…` e `ƒ` — que colidem com o
símbolo de xeque e com a reticência de lance do próprio livro.
Critério: nos dois PDF entregues, `page.get_text()` tem de conter `Nf6`, `Nb3`, `Qxh7`,
`Bxh7`, `Rc1` e `Rfd1` — hoje **nenhum dos dois contém nenhum deles**. Isto fecha o R2 de
graça: com a camada de texto certa, a comparação de tokens vê as peças sozinha.

Os não bloqueantes 1, 2 e 3 (espaço desigual entre elementos equivalentes, título órfão na
p2, `g` fora da fila) não são condição de aprovação, mas os três estão a uma linha de código
cada e os três são defeitos que a carta nomeia literalmente. O não bloqueante 4 (a cabeça
corrente sem acentos) pede uma verificação no `textaudit.py`: *nenhuma cadeia em português
pode conter uma palavra que ganhe diacrítico ao ser normalizada* — teria apanhado `peoes` e
`Capitulo` antes de a folha sair.

**Fechados R1–R4, aprovo.** Não peço mais do que isto e não aceito menos.

---

## Nota final, sobre rigor e obstrução

A carta §5.5 diz que reprovar indefinidamente é tão inútil como aprovar cedo demais, e o
enunciado deste ciclo avisa que quatro ciclos de reprovação com a frente a melhorar
mediamente começariam a ser obstrução. Levei isso a sério, e digo onde caí.

A frente melhorou de verdade e em quase tudo: 5º/6º/7º de sete no ciclo 1, 4º de 6 no
ciclo 3, **3º de 6 agora**, contra um conjunto mais forte e num teste que desta vez foi
mesmo cego. Q1 e Q2 estão fechados e eu olhei para confirmar. Q3 e Q4 reproduzem os números
que alegam. A folha é reprodutível ao span. O construtor encontrou dois defeitos sozinho, a
olho, e corrigiu o instrumento do crítico anterior em vez de discutir com ele.

Reprovo mesmo assim, e a razão não é gosto — é que as duas condições que restam da barra do
ciclo 1 falham por medição, não por opinião:

* **«Nenhum defeito na nossa que não seja apontado também nas referências.»** A linha de
  meio de parágrafo a 55 % da medida não existe em A, B, C nem D (0 em 204 linhas
  verificadas). O figurino misturado não existe em nenhuma das cinco. A camada de texto sem
  notação não é comparável porque quatro das cinco referências são PDF de produção e as
  quatro deixam a notação legível — verifiquei em C e em D.
* **«Pelo menos uma vantagem clara e medida.»** A que a Fase 1 encontrou a nosso favor é
  produzida pelo primeiro desses defeitos, e a que o ciclo 4 escolheu é medida por um
  instrumento que não distingue um cavalo de uma dama. Provei o segundo por sabotagem, não
  por argumento.

Nenhum dos quatro pedidos acima é reconstrução. Dois são um ramo de código cada, um é uma
tabela de glifos e o quarto é um `ToUnicode`. **O ciclo 6 é cirurgia curta, e é o ciclo em
que isto passa.**

---

```
VEREDITO: REPROVADO
CICLO: 5
FRENTE: F7 (Tipografia)
```

**A razão, numa linha:** a amostra ficou em 3º de 6 num teste cego que desta vez foi cego —
condição cumprida — mas apontei nela quatro defeitos que não existem em nenhuma das cinco
referências (linha de meio de parágrafo a 55 % da medida, figurino misturado por tipo de
peça, camada de texto sem notação, cabeça corrente sem acentos), e a única vantagem alegada
do ciclo cai por sabotagem: com uma dama no lugar do cavalo no primeiro lance do livro,
`compare_exporters.py` continua a imprimir «222 tokens, idênticos, 0 divergências».
