# F5 · ciclo 2 — arbitragem por região e integridade da notação

> **Data:** 2026-09-10, com as §§4–5 acrescentadas em **2026-09-11** ·
> **Frente:** F5 (OCR de texto) · **Item:** HANDOFF §4.1
> Ambiente: `.venv` na raiz, Python 3.11.9, PyMuPDF 1.28.2.
> Todo número desta página traz ao lado o comando que o produziu.
> Acervo: `C:\Python-Chess2\ChessVisionOFF_Puro\PDF` (`CORPUS.md` §0).

---

## 0. O que este ciclo entrega

1. **O laço por região existe** (`src/caissa/ocr/page.py`). Até agora **nada no
   produto chamava o árbitro** — a peça que corta a página e roda a cascata por
   região nunca tinha sido escrita.
2. **O defeito conhecido do nível 0 está fechado**, mas **não pelo laço**. O
   plano de registro (`F5_REPORT.md` §5, item 1) supunha que arbitragem por
   região resolveria as páginas 202 e 245 do Gaprindashvili. **Medi, e não
   resolve** — §1. Quem resolve é um sinal novo, `mangled_move_ratio` — §2.
3. **O defeito é muito maior do que duas páginas.** Varrendo o acervo inteiro:
   **16 dos 33 livros com camada de texto têm a notação danificada**, e todos
   eram aceitos com confiança 0,98 — §2.4.
4. **Escalar vale a pena, mas não pelo motivo esperado** (medido em
   2026-09-11). A camada de texto perde **0,0 % — zero — de 1.432 letras de
   peça**; o Tesseract também não lê os figurinos, mas erra como uma cifra de
   substituição recuperável em vez de como ruído. E no controle limpo a
   direção se inverte, que é por que o limiar existe — §4.
5. **Dois defeitos achados ao rodar o laço de ponta a ponta** — §5. Cortar a
   página **lavava o veredito dela** (a p202 caía de 0,55 para 0,98 e não
   escalava nada), e o **16.º portão cego**: a calibração zera o Tesseract em
   12 de 12 páginas, então o nível 0 vence sempre que produz qualquer texto. O
   primeiro está consertado; do segundo consertei metade e **deixei o resto
   registrado em vez de ajustar o número por olho**.
6. **O corretor de cifra existe** — §6. Na saída do Tesseract, o ilegível cai
   de **78,5 % para 34,3 %** no Gaprindashvili, e 45,7 % dos lances passam a
   ter casa certa com a peça reduzida a quatro candidatas. Ele **não adivinha**
   a peça: resolve a dama pela promoção e marca o resto como buraco, para a
   reprodução por legalidade decidir. Dezoito páginas de controle voltam byte
   a byte.
7. **A cadeia inteira produz lance legal pela primeira vez** — §7. Diagrama →
   FEN → Tesseract → cifra → tronco → legalidade: **12 lances legais de 18
   extraídos em 6 páginas**. O elo que faltava não era a F2 e sim
   `RegionKind.MOVETEXT`, que estava na taxonomia desde a F1 **sem nada jamais
   atribuí-lo**.

> **O que este ciclo NÃO faz.** Nenhuma página sai daqui com a notação
> *inteiramente* consertada: a peça de 45,7 % dos lances recuperados fica para
> a reprodução por legalidade decidir, e isso precisa de uma posição — ligar o
> diagrama (F3/F4) ao texto do lance é trabalho de pipeline que a F2 ainda não
> permite. O que sai daqui é o defeito **nomeado, medido e em grande parte
> desfeito**; a §5.3 explica a distância que resta.

---

## 1. O plano de registro estava errado, e a medição é esta

`F5_REPORT.md` §5 item 1 diz, textualmente, que falta «o laço que corta a
página em regiões, chama o nível 0 por região, e deixa o nível 1 assumir só as
regiões de figurino», e que isso é «a correção direta do único erro conhecido
do nível 0».

**Primeira coisa que fiz foi medir se seria.** Não é.

Rodei `analyze_page` sobre a p202 antes de escrever uma linha do laço. Ela
devolve **duas** regiões, e a segunda tem 1.177 caracteres misturando prosa
correta e lances destruídos — o índice de dano da região (0,38 sobre 8 tokens)
é praticamente o da página. Olhando linha a linha, o motivo é evidente e é
definitivo (`page.get_text("dict")`, p202):

```
y=173.1  "I ... 'it'g4!! White is in zugzwang! 2 1'.c4 @xh4! Now Black is the fust to "
y=226.1  "For the present White cannot play 1 !txg7 Wxg7 2 .tel l:txcl+ (check!). "
y=240.2  "I c;!;>g2! dxe4 There is nothing better. 2 l:txg7 »xg7 3 ilcl! .l:i:xcl 3 ... .l::th8 "
```

**A prosa e os lances destruídos dividem a mesma linha.** Nenhum corte
geométrico — parágrafo, linha ou coluna — os separa. A unidade do defeito é o
**token**, não a região.

A conclusão está pinada na docstring de
`tests\unit\ocr\test_text_layer.py::test_gaprindashvili_third_party_ocr_layer`,
com a linha citada, para que a próxima pessoa não refaça o mesmo plano.

Isso não invalida o laço: ele é necessário por outros motivos (§3) e é a única
porta de entrada de página que a frente tem. Mas ele **não** fecha este
defeito, e o relatório anterior prometia que fecharia.

---

## 2. O sinal que fecha o defeito — `mangled_move_ratio`

### 2.1 O que ele mede

Uma fonte de figurinos mapeia o cavalo para um código privado. Quando o PDF é
re-OCR'd, ou embutido sem um ToUnicode utilizável, aquele código volta como as
letras latinas que calharem de estar no mesmo lugar:

| era | virou | livro |
|---|---|---|
| `♕d6+` | `'i'd6+` | Gaprindashvili p202 |
| `♖h7` | `l:th7` | Gaprindashvili p202 |
| `♘xe5` | `ll'lxe5` | Aagaard p222 |
| `♕h5` | `ti'h5` | Aagaard p148 |
| `Лd7` | `Jld7` | Boleslávski p168 |
| `a8` | `á8` | Capablanca p410 |

O teste é **unilateral por construção**: um lance danificado **mantém a casa** —
coluna e linha são latino comum, que nenhuma fonte de figurinos toca — e perde
a peça. Então: um token que contém uma casa, não é notação válida, não está no
léxico, e carrega um caractere que a notação não tem como produzir.

`src/caissa/ocr/lexicon.py`: `is_mangled_move`, `is_move_token`,
`mangled_move_ratio`, `NOTATION_ALPHABET`.

### 2.2 O alfabeto é derivado, não copiado

O décimo-segundo portão cego deste projeto foi «duas tabelas coincidentes —
acertava por coincidência, não por construção». `NOTATION_ALPHABET` e a regex
`_NOTATION` agora saem **das mesmas constantes** (`_PIECE_LETTERS`,
`_LINK_MARKS`, `_ANNOTATION_MARKS`), e um teste reprova se divergirem.

A regex passou a ser **construída** a partir dessas constantes em vez de
tê-las escritas à mão dentro dela. Antes de aceitar a refatoração, provei que
ela não mudou comportamento: 400.000 tokens sorteados sobre o alfabeto de
notação, casados contra a versão antiga e a nova.

```
tokens sorteados: 400.000
divergências: 148
divergências SEM figurino (deveriam ser ZERO): 0
```

As 148 divergências são **todas** do figurino Unicode (U+2654–U+265F), que a
regex antiga não conhecia e agora conhece — a única mudança pretendida. Sem
essa adição, um livro nativo que use `♘f3` de verdade seria condenado inteiro:
era o falso positivo catastrófico deste sinal, e está fechado por construção.

Foi uma verificação de migração, de uso único — a versão antiga da regex não
sobrevive em lugar nenhum, então não há o que rodar de novo. O que **fica**
rodando é `test_the_alphabet_is_derived_and_not_copied`, que reprova se as duas
tabelas voltarem a divergir, e `CLEAN_TOKENS`, que fixa notação correta nos
oito idiomas mais o figurino.

### 2.3 O limite, e de onde ele vem

`max_mangled_move_ratio = 0,15`, com piso de 12 lances julgados.

```
.venv\Scripts\python.exe benchmarks\notation_integrity.py --what books
```

| livro | páginas | mediana | mín | máx | acima de 0,15 |
|---|---:|---:|---:|---:|---:|
| Gaprindashvili E8 (dano conhecido) | 42 | 0,341 | **0,195** | 0,459 | 42/42 |
| Aagaard E1 | 44 | 0,292 | 0,024 | 0,648 | 35/44 |
| Nunn E2 | 60 | 0,125 | 0,000 | 0,625 | 27/60 |
| **Dvoretsky E1 — controle** | 60 | 0,000 | 0,000 | **0,000** | 0/60 |
| **Boleslávski E6 — controle** | 50 | 0,000 | 0,000 | **0,065** | 0/50 |

**110 páginas de controle, máximo 0,065.** O mínimo do Gaprindashvili sobre 42
páginas é **0,195** — três vezes o máximo do controle. O limite fica na folga,
com margem dos dois lados.

**O limite não foi escolhido para pegar página nenhuma.** A p202 do
Gaprindashvili chegou a ficar de fora, em 0,146, e o registro daquele momento
era «fica registrado como falha». Ela entrou depois, por um **conserto de
denominador** e não por mexer no limite: `is_move_token` contava `1-0` e `0-1`
como lances, porque são notação válida e têm hífen. Resultados não são lances;
tirá-los do denominador levou a p202 de 0,146/89 para **0,157/83**.

### 2.4 O defeito não eram duas páginas — são dezesseis livros

```
.venv\Scripts\python.exe benchmarks\notation_integrity.py --what sweep     # 13,1 s
livros: 13 com notação danificada · 3 marginais · 17 limpos · 13 sem camada de texto
```

| | livros |
|---|---:|
| sem camada de texto com lances (é imagem) | 13 |
| camada limpa — mediana 0,000 | 17 |
| mediana entre 0,03 e 0,10 | 3 |
| **mediana acima de 0,10 — notação danificada** | **13** |

**São 46 arquivos, não 50.** `CORPUS.md` §0 diz «50 arquivos»; o diretório tem
46. Ou quatro saíram, ou o número sempre foi aproximado — de todo modo o
`CORPUS.md` está desatualizado nesse ponto.

A fronteira em 0,10 é sensível ao tamanho da amostra: com `--cap 40` um livro
atravessa e a conta vira 14 e 2. **O número estável é 16** — livros com mediana
acima de 0,03 — e é esse que vale citar.

Entre eles: `Juravliov` (0,516), `Secrets of Chess Training` (0,349),
`Burgess — Gambit` (0,336), `Nunn — Minor Piece Endings` (0,312),
`Yusupov` (0,306), `Euwe Band 7`, `Aagaard`, `Polgar 5334`.
**Todos eram aceitos a 0,98.**

Dois deles — Aagaard e Nunn — são os **controles E1/E2 do próprio corpus**,
usados até agora para provar que o detector não é severo demais. São
digitalizações re-OCR'd: toda fonte de suas páginas é um subconjunto
sintetizado `Fd######-Identity-H`. **`CORPUS.md` §2 E1 precisa da mesma
correção que Flores Rios recebeu**: «E1» não implica «camada de texto boa».

### 2.5 Não achei um falso positivo

Inspecionei à mão todo token acusado nas duas páginas de maior índice entre os
livros «limpos» — os únicos candidatos plausíveis a falso positivo do acervo:

| página | índice | tokens acusados | veredito |
|---|---:|---|---|
| Capablanca p410 | 0,154 | `b7-á8`, `á7-d7`, `á1-c1`, `á7-c7` | **dano real** — a coluna `a` voltou como `á` |
| Boleslávski p168 | 0,125 | `JIfd8`, `Jld2` | **dano real** — o `Л` voltou como `Jl` |

Zero falsos positivos em 46 livros. O único que houve na primeira versão —
`f2-pawn` e `f4-pawn`, no Dvoretsky — está fechado (composto cujo outro lado é
palavra) e pinado como teste.

### 2.6 O que o veredito faz com o sinal

Duas faixas, em `TextLayerThresholds`:

| índice | veredito | confiança | por quê |
|---|---|---|---|
| > 0,60 | **reprovado** | 0,00 | não resta notação aproveitável |
| > 0,15 | **aceito**, notação sinalizada | **0,55** | a prosa é correta e vale mais que os lances perdidos |

0,55 não é um número redondo: é **baixo o bastante para não passar na barra de
0,82 que o árbitro impõe ao nível 0**, de modo que um motor de OCR de verdade
passa a concorrer pela página. É para isso que existe uma cascata. A camada
continua **aceita** porque jogar fora uma prosa correta para salvar os lances é
a troca pior.

Efeito nas páginas pinadas
(`.venv\Scripts\python.exe benchmarks\notation_integrity.py --what verdicts`):

| página | antes | agora | índice |
|---|---|---|---|
| Gaprindashvili p202 | aceita 0,98 | aceita **0,55** | 0,157 / 83 lances |
| Gaprindashvili p245 | aceita 0,98 | aceita **0,55** | 0,231 / 121 |
| Aagaard p148 / p222 / p260 | aceitas 0,98 | aceitas **0,55** | 0,467 / 0,292 / 0,255 |
| Nunn p120 / p200 | aceitas 0,98 | aceitas **0,55** | 0,216 / 0,315 |
| Dvoretsky, 5 páginas | aceitas 0,98 | **inalteradas** | 0,000 |
| Boleslávski, 5 páginas | aceitas 0,70 | **inalteradas** | ≤ 0,065 |

### 2.7 Prova de vitalidade

`tests/unit/ocr/test_notation_integrity.py::test_the_old_signals_are_blind_to_this_damage`
pega uma página de prosa e lances corretos, **danifica só os glifos de peça**, e
mede os três sinais que deveriam ter percebido. Todos continuam passando:
`nonword_ratio` abaixo de 0,45, `dictionary_hit_rate` acima de 0,12,
`implausible_char_ratio` abaixo de 0,15 — e mal se movem. O sinal novo sai de
0,000 para acima de 0,15 na mesma página.

É a prova de que o portão não é redundante, e é a razão de ele existir.

O outro lado também está pinado: `test_the_gate_fails_when_the_damage_is_removed`
exige 0,000 exato com a sabotagem desfeita, em quatro proporções de prosa. Um
detector que dispara em tudo é tão inútil quanto um que não dispara em nada.

### 2.8 Custo

Mediana de 3 execuções (`CORPUS.md` §5), 40 páginas do Gaprindashvili com texto
de verdade — média de 2.203 caracteres, porque medir sobre as páginas em branco
do livro daria um número bonito e falso:

| | ms por página |
|---|---:|
| só o sinal de notação | **0,71** |
| veredito completo do nível 0 | 14,18 |

**O sinal é 5 % do veredito.** Ele *não* reaproveita a tokenização dos outros
sinais — `mangled_move_ratio` chama `tokenize` por conta própria — e ainda
assim não muda a ordem de grandeza de nada. Unificar os laços é uma otimização
possível e, a 0,71 ms, não vale a acoplagem.

---

## 3. O laço por região

`src/caissa/ocr/page.py` — `PageTask` → `PageRecognizer.run` → `PageOutcome`.

O que o torna mais que um `for` está abaixo, e cada item tem teste próprio —
**cinco deles com a sabotagem que os faz reprovar**, porque um portão que só
devolve zero é indistinguível de um portão cego (`CRITIC_CHARTER.md`).

### 3.1 Espaços de coordenadas

O nível 0 lê o PDF e quer um `clip` em **pontos**; todo outro motor lê pixels e
quer um **recorte**, cujas caixas voltam relativas ao recorte. Errar isso produz
**texto certo e caixas silenciosamente deslocadas** — que nenhum teste que
compare strings pega nunca.

Regra única: **leiaute em pontos, resultados no espaço de pixels da página
inteira.** O nível 0 já emite pixels dado `scale`; qualquer outro motor tem o
resultado transladado pela origem da região na saída.

**Sabotagem 1** — removi a translação:

```
FAILED test_a_region_result_lands_in_page_space
FAILED test_the_offset_is_not_zero_by_accident
```

O segundo teste existe porque uma região que começasse em (0,0) tornaria a
translação um no-op e o primeiro teste passaria contra código que não translada
nada. Ele exige que a origem seja grande (`ox > 20 and oy > 200`).

**E ainda assim havia um bug aqui, e nenhum dos dois pegou.** Achei relendo o
próprio código depois de os testes ficarem verdes:

> `_run_region` transladava **o que o árbitro devolvesse**. Correto para um
> motor que só viu o recorte; errado para o nível 0, que recebe o `clip` e o
> `scale` e já responde em coordenadas de página. Com um raster junto, um
> parágrafo a 600 pt voltava em **y = 2.458 px numa página de 1.754 px** — fora
> da página, exatamente no dobro do próprio deslocamento.

O motivo de ter passado é o de sempre: o teste que cobria o nível 0
(`test_level_zero_boxes_are_already_in_page_space`) **não passa raster nenhum**,
então o recorte é `None`, a origem é (0,0) e a translação é um no-op. Um portão
que não conseguia ver a falha para a qual foi escrito.

O conserto não é uma asserção melhor naquele teste: é
`test_level_zero_boxes_survive_a_raster`, que roda a **mesma página das duas
formas** e exige a mesma resposta. Restaurando o bug (**sabotagem 4**):

```
FAILED test_level_zero_boxes_survive_a_raster
```

Foi o décimo-quarto instrumento cego deste projeto, e o primeiro achado por
releitura em vez de por crítica adversarial — o que só reforça a regra: um
portão verde não é evidência de nada até alguém tentar quebrá-lo.

### 3.2 Uma região curta não pode ser condenada por ser curta

O nível 0 chama de «digitalização» qualquer coisa com menos de 24 caracteres.
Certo para uma página, **catastrófico para uma região**: julgada sozinha, toda
titulação, legenda e fólio do acervo seria reprovada e mandada ao OCR. Uma
região sem texto próprio suficiente **herda o veredito da página**.

**Sabotagem 3** — removi o piso:

```
FAILED test_a_short_region_inherits_the_page_verdict
FAILED test_body_text_drops_the_folio
```

### 3.3 O que o veredito por região compra — medido, não suposto

**A sabotagem 2 passou em tudo, na primeira tentativa.** Desliguei o veredito
por região inteiro — toda região herdando o da página — e os 13 testes
passaram. O portão estava cego: o teste que eu tinha escrito («só a região ruim
escala») passa mesmo sem veredito por região, porque **o termo de
plausibilidade do árbitro já pega lixo sozinho**.

Foi preciso um caso onde o veredito por região faça diferença de fato: uma
página com 100 lances corretos em cima e 15 destruídos embaixo. A página lê
**0,087** — abaixo da barra, veredito limítrofe 0,80. O bloco de baixo lê
**0,667** sozinho — acima de 0,60, **reprovado**.

Medindo os dois lados, com `PageConfig(min_chars_for_own_verdict=…)` no lugar
da sabotagem:

| | com veredito por região | sabotado (só página) |
|---|---|---|
| bloco bom | 0,98, aceito no nível 0 | **0,80** — puxado para baixo por dano em outra parte da página |
| bloco ruim | nível 0 devolve **vazio**, escala limpo, mock aceito a **0,901** | nível 0 devolve o lixo a 0,80, escore 0,450; **nenhum motor atinge o limite**, vencedor escolhido pelo ramo «melhor de um lote ruim» a 0,643 |

**O motor vencedor é o mesmo nos dois casos.** O que muda é a confiança do
bloco bom, e o fato de o lixo nunca entrar como candidato. Foi assim que ficou
escrito no teste — a versão anterior da docstring afirmava mais do que a
medição sustentava.

Com o teste corrigido, a sabotagem 2 reprova:

```
FAILED test_a_diluted_page_hides_a_destroyed_block_and_the_region_does_not
AssertionError: as regiões foram julgadas pelo veredito da página, não pelo próprio
```

### 3.4 O veredito desce pelo árbitro, sem quebrar quem não o espera

Para o §3.2 funcionar, o veredito calculado pelo laço tem de chegar ao nível 0
através do árbitro. `RegionTask` ganhou um campo `verdict`, e `Arbiter._invoke`
só o repassa a um `recognize_page` **que declare o parâmetro** — pergunta à
assinatura em vez de supor, com o resultado em cache pela função subjacente
(uma função ligada é um objeto novo a cada acesso e anularia o cache).

`verdict` é uma extensão do ponto de entrada do nível 0, não parte do
Protocolo. Sem a guarda, o terceiro adaptador de nível 0 que alguém escrever
morre de `TypeError` na primeira página. **Sabotagem 5**, guarda removida:

```
FAILED test_an_engine_without_the_keyword_is_not_handed_one
src\caissa\ocrrbiter.py:407: TypeError
```

### 3.5 Página inteira, quando cortar é pior

Três caminhos voltam a uma arbitragem única, e cada um tem teste:

| condição | por quê |
|---|---|
| sem página de PDF | não há de onde tirar linhas sem antes reconhecer — e um motor com `handles_layout` faz o próprio leiaute melhor do que recortes |
| camada da página reprovada | não há o que salvar por região; cortar só paga o custo trinta vezes |
| mais de 50 % das regiões escalaram | o Tesseract vê o leiaute; os recortes tiram isso dele |
| mais de 60 regiões | teto contra página patológica |

### 3.6 Mobiliário volta como região

`analyze_page` monta regiões a partir da ordem de leitura, que exclui cabeçalho,
fólio e rótulo de diagrama de propósito. Mas «fora do corpo» não é «fora da
página»: o cabeçalho carrega o título do capítulo e o fólio é o que um índice
aponta. Eles voltam como uma região por linha, e é `body_text` que os filtra.

---

## 4. Escalar vale a pena? — medido em 2026-09-11

A §2.6 rebaixou dezesseis livros para 0,55 **para que um motor de OCR pudesse
concorrer**, e deixou em aberto se ele ganharia. Era a pendência nº 2 da §7.
Esta é a resposta, e ela não é «sim» nem «não».

```
.venv\Scripts\python.exe benchmarks
otation_integrity.py --what recovery
26,6 s · 24 páginas · Tesseract 5.5.0 a 300 dpi (≈1,1 s por página)
```

| livro | motor | lances com peça | peça certa | erro de 1 caractere | formas distintas |
|---|---|---:|---:|---:|---:|
| Gaprindashvili E8 | nível 0 | 860 | **0,0 %** | 15,1 % | **204** |
| | tesseract | 737 | 12,8 % | **96,7 %** | 51 |
| Aagaard E1 | nível 0 | 158 | **0,0 %** | 37,3 % | 49 |
| | tesseract | 115 | 15,7 % | **93,0 %** | 31 |
| Nunn E2 | nível 0 | 414 | **0,0 %** | 31,2 % | 41 |
| | tesseract | 403 | 21,8 % | **98,0 %** | 34 |
| **Dvoretsky E1 — controle** | **nível 0** | 172 | **98,8 %** | 98,8 % | **7** |
| | tesseract | 62 | 11,3 % | 98,4 % | 16 |

«Peça certa» é a fração de lances cuja letra de peça sobreviveu — `K`, `Q`,
`R`, `B`, `N`, `P`. «Erro de 1 caractere» é a fração em que o que sobrou na
frente da casa é **um único caractere**, seja ele qual for. Lances de peão são
excluídos: não têm glifo de peça a perder.

### 4.1 Três conclusões, e nenhuma era a esperada

**A camada de texto perde *todas* as peças.** Não «a maioria»: **0,0 % de 1.432
lances** em três livros. Para notação, a camada desses livros não está
degradada, está perdida. Isso valida o rebaixamento da §2.6 muito mais
fortemente do que o índice de 0,15 sugeria.

**O Tesseract também não lê os figurinos** — 12,8 a 21,8 %. Quem esperava que
o OCR resolvesse errou, e eu era um deles. Nenhum dos dois motores transforma o
glifo de um cavalo em `N`, porque nenhum dos dois é um modelo de figurinos.

**Mas as duas falhas têm formas diferentes, e só uma é recuperável.** O
Tesseract erra como uma **cifra de substituição quase perfeita**: 93–98 % dos
erros são de um caractere só, e as formas colapsam em `W` (dama), `H` (torre),
`S` (rei), `B`/`A` (bispo/cavalo). A camada de texto erra como **ruído**: 204
formas distintas num livro só, `i.`, `l:t`, `'it>`, `.l:t`, ``. **Uma cifra
se inverte; ruído não.** É essa a diferença que justifica escalar, e não a
acurácia bruta.

### 4.2 O controle inverte tudo, e é por isso que o limiar existe

No Dvoretsky a camada acerta **98,8 %** das peças com **7** formas distintas —
é notação correta, lida corretamente. O Tesseract despenca para **11,3 %**.

**Escalar uma página limpa seria o erro pior.** O limiar de 0,15 não está lá
para ser cauteloso: está lá porque do outro lado dele o OCR destrói o que a
camada acerta. O Dvoretsky nunca o cruza (medido na §2.6: escore 0,978).

A prova de vitalidade deste portão é a própria parametrização: o mesmo teste
afirma coisas **contraditórias** para `damaged` e para `clean` — `correct == 0`
de um lado, `correct > 0,90` do outro — e as duas passam. Um teste que passasse
nos dois com a mesma asserção não estaria medindo nada.

### 4.3 O que isso abre

Se o dano do Tesseract é uma cifra estável dentro de um livro, **um corretor de
substituição recupera a notação dos dezesseis livros**. A tabela acima já dá o
mapa do Gaprindashvili (`W`→♕, `H`→♖, `S`→♔) e do Nunn. Isso é trabalho de
frente F6, precisa de um mapa por fonte e de verificação por legalidade
(`notation/legality_repair.py` já existe), e **não foi feito**.

---

## 5. Duas coisas quebradas, achadas ao rodar o laço de ponta a ponta

A §4 comparou os dois motores **por fora** do `PageRecognizer`. Rodá-lo de
verdade — nível 0 real, Tesseract real, páginas reais — era a pendência nº 3, e
revelou dois defeitos. Um eu tinha acabado de introduzir; o outro estava lá
desde o começo da frente e é o mais grave dos dois.

### 5.1 Cortar a página lavava o veredito dela

A Gaprindashvili p202 é acusada a **0,55**. Cortada em regiões, as duas metades
voltavam a **0,98**:

| unidade | confiança | danificados | por quê |
|---|---:|---:|---|
| página | **0,55** | 0,157 / 83 | acusada, corretamente |
| região 0 | 0,98 | 0,273 / **11** | o piso de 12 lances faz o teste **abster-se** |
| região 1 | 0,98 | **0,139** / 72 | passa raspando por baixo da barra de 0,15 |

Uma metade se esconde atrás do tamanho da amostra e a outra atrás da barra.
O resultado é que **o laço escalava *nada* nessa página** — o veredito de
página sozinho era estritamente melhor que o laço, e eu tinha acabado de
escrever o laço.

O conserto **não** é baixar a barra por região. Figurino danificado é
propriedade da **fonte**, e a fonte é a mesma na página inteira: uma região com
menos peças mostra menos dano sem ser mais confiável. A regra, então:

> Uma região pode ser julgada **pior** que a página — é para isso que existe
> arbitragem por região — mas nunca **melhor**, num defeito que a página mediu
> com mais evidência.

`PageRecognizer._cap_by_page`. Depois do conserto, a p202 escala as duas
regiões e a Nunn p200 escala 11 de 11. O controle Dvoretsky continua escalando
**zero**, em 0,06 s.

**Sabotagem 6** — teto removido:

```
FAILED test_cutting_a_page_up_must_not_launder_its_verdict
```

### 5.2 O 16.º portão cego: a cascata além do nível 0 era decorativa

Com o teto no lugar, o Tesseract finalmente roda. E **perde todas as vezes**.

A causa não é julgamento, é um **erro de categoria na tabela de calibração**:

```
"tesseract": EngineCalibration(floor=0.55, gamma=1.4, worst_word_weight=0.35)
#  o piso veio de «a confiança de PALAVRA do Tesseract raramente cai de 0,60»
#  e é aplicado a um AGREGADO DE PÁGINA
```

Medido em 12 páginas de cinco livros, através do caminho real
(`Arbiter._confidence_of`):

| | valor |
|---|---|
| confiança **mínima** de palavra | **0,000 em 12 de 12 páginas** |
| agregado cru (média × 0,65 + mínimo × 0,35) | 0,216 a 0,532, mediana 0,493 |
| piso da calibração | **0,55** |
| confiança calibrada | **0,000 em 12 de 12** |

Dois erros se compõem:

**O termo da «pior palavra» era uma constante.** Toda página inteira tem um
artefato lido a zero — uma sujeira, uma coordenada de diagrama, um pedaço de
fio. O mínimo é 0,000 sempre, em todo livro e todo motor, então o peso de 0,35
deixa de ser sinal e vira **multa fixa de 35 %**. Corrigido: o termo agora é um
**quantil baixo** (`OcrResult.weak_word_confidence`, padrão 5 %), que preserva a
intenção da ASSETS §2.11 — não deixar a média esconder o que está errado — sem
morrer no primeiro artefato. Páginas zeradas: **12/12 → 6/12**.

**O piso é da grandeza errada** e continua errado. Aplicar um piso medido em
palavras a um agregado de página põe o corte no meio da distribuição, e
`gamma=1,4` achata o que sobra para 0,01–0,07.

**Não ajustei o piso, de propósito.** Escolher o número por olho até o
Tesseract ganhar é exatamente como se compra um portão; a própria docstring da
tabela diz que calibração honesta exige o corpus rotulado da SPEC §11.2, que
não existe. O estado fica **registrado como teste**
(`test_the_cascade_past_level_zero_is_currently_decorative`), que deve começar a
reprovar no dia em que o piso for ajustado.

**A precisão importa aqui, então: a cascata não está morta, está incapaz de
*preferir*.** Numa página só de imagem o nível 0 devolve vazio e pontua 0,000,
e aí o Tesseract ganha:

| página | vencedor | escore do Tesseract | confiança |
|---|---|---:|---:|
| Flores Rios p116 (só imagem) | **tesseract** | 0,390 | **0,00** |
| Gaprindashvili p28 (só imagem) | **tesseract** | 0,179 | **0,00** |

Ele ganha **por ausência de adversário**, com confiança calibrada zero — não
por mérito. A regra exata é esta: *sempre que o nível 0 produz qualquer texto,
ele vence*, porque uma camada aceita vale 0,55 a 0,98 e o Tesseract está preso
perto de 0,00. Os níveis 2 e 3 herdariam o mesmo problema se fossem instalados.

**Sabotagem 7** — volta ao mínimo em vez do quantil:

```
FAILED test_the_quantile_is_what_the_arbiter_actually_blends
```

### 5.3 A consequência honesta para a §2.6

Rebaixar uma página danificada a 0,55 **muda a confiança e o registro do
motivo, mas não muda o texto**. O escalonamento acontece — está medido — e o
motor que concorre não consegue ganhar. O benefício fica represado até que
**uma** destas duas coisas exista:

- o piso de calibração ajustado contra o corpus rotulado (§11.2 da SPEC), ou
- o corretor de substituição da §4.3, que não depende de o Tesseract ganhar a
  arbitragem: ele pode ser aplicado ao texto do Tesseract quando a notação da
  camada estiver acusada.

A mudança da §2.6 continua certa — a camada acerta **0,0 %** das peças e dizer
0,98 sobre isso era mentira. Mas ela ainda **não** conserta nenhuma página, e o
relatório anterior não deixava isso claro.

---

## 6. O corretor de cifra — 2026-09-11

A §4.3 apontou o caminho e a §9 chamou de «o único item que conserta páginas em
vez de medi-las». Está construído: `src/caissa/ocr/notation/cipher.py`.

### 6.1 Onde ele opera, e por que não no nível 0

Sondei primeiro se a cifra podia ser invertida **na camada de texto**, que seria
mais barato. Não pode:

```
Gaprindashvili, 7 páginas, caracteres imediatamente antes de uma casa:
  23 fontes distintas desenham esses caracteres, todas "*Times New Roman-NNNNN"
  dentro de UMA fonte: 81 a 97 formas distintas para ~170-200 ocorrências
```

Vinte e três subconjuntos sintetizados, cada um com quase uma forma distinta
por ocorrência. **Não é cifra, é ruído** — confirmando a §4 no nível do
caractere. O corretor lê a saída do Tesseract, onde 93–98 % dos erros são de um
caractere só.

### 6.2 O que ele decide, e o que se recusa a decidir

`infer_cipher` infere o **alfabeto** da cifra e resolve só o que tem prova.
A única prova disponível sem posição é a **promoção**: `f8=W` é um peão
chegando à oitava, e em partidas publicadas isso é dama — subpromoção é evento
nomeado. Então `W` = dama, medido e conferido contra a imagem da página.

O resto ele **marca como buraco** (`?h7`) em vez de adivinhar. Frequência
distinguiria torre de rei com uma taxa de acerto, e um palpite que *parseia* é
exatamente o modo de falha que este projeto já encontrou dezesseis vezes. Quem
decide o resto já existe e não é este módulo:
`notation/legality_repair.py` toma os lances legais da posição como espaço de
candidatos, e `candidate_locales()` entrega as hipóteses na forma que ele
espera — uma cifra **é** um locale, `W`/`H` está para o inglês como `D`/`T`
está para o alemão.

### 6.3 Quanto recupera

```
.venv\Scripts\python.exe benchmarks
otation_integrity.py --what decode
```

| livro | ilegível antes | ilegível depois | peça conhecida, casa conhecida |
|---|---:|---:|---:|
| Gaprindashvili E8 | 78,5 % | **34,3 %** | 45,7 % viram «casa certa, peça a decidir» |
| Nunn E2 | 74,8 % | **35,7 %** | 64,6 % |
| Aagaard E1 | 62,9 % | **38,2 %** | 53,9 % |

E o SAN plenamente válido sobe de 21,5 % para 25,1 % no Gaprindashvili — são as
promoções, o único lugar onde a peça fica **decidida** sem posição.

Isso não é «os lances estão consertados». É a diferença entre **redigitar** e
**revisar**: um token que não era notação passa a ser um lance com destino,
captura, desambiguação e marca de xeque corretos, e a peça reduzida a quatro
candidatas que uma reprodução por legalidade elimina em um ou dois lances.

### 6.4 O que impediu o corretor de ser um jeito novo de estragar livros

Este módulo só pode causar dano numa direção: deixar de decodificar uma página
danificada a mantém como estava; decodificar uma página **sã** destrói notação
correta, e em silêncio, porque a saída continua parecendo notação.

Quatro falsos positivos reais apareceram nos controles, cada um exigindo uma
guarda diferente — e nenhum deles aparece em texto sintético:

| o que quebrou | a guarda |
|---|---|
| `Кс4` russo lido como cifra | as letras de peça vêm de **todos** os locales, por construção a partir de `LOCALES` |
| `Kd2` russo com **K latino** | dobra de homoglifos — é outro defeito (§6.5), não esta cifra |
| `Кра8—b7` com travessão | a lista de traços Unicode, a mesma que o `legality_repair` mantém |
| um livro **português** que imprime `Qf6` em inglês | a língua da prosa **não** é a língua dos lances |

O quarto foi o pior: dizer ao decodificador que a página era portuguesa — que
era — o fez reescrever **oito lances corretos** em `?f6`, `?xg3`, `?d2`. Por
isso o padrão aceita as letras de **todos** os idiomas, e o parâmetro se chama
`notation_lang` com um aviso na docstring.

**Isso custa recall e o número está registrado:** `S`, `A` e `B` são letras de
peça em algum idioma, então um símbolo de figurino que caia neles fica sem
decodificar. Com o alfabeto estreito o ilegível do Gaprindashvili cairia de
34,3 % para 4,9 % — e foi o alfabeto estreito que reescreveu a página
portuguesa. **Reabrir isso é trabalho da reprodução por legalidade, não de um
alfabeto mais largo.**

Controles: **18 páginas de quatro livros, três alfabetos e três idiomas de
notação, byte a byte** (`test_real_books_with_correct_notation_survive_untouched`).

### 6.5 Duas guardas estavam cegas, e a sabotagem mostrou

**Sabotagem 8** (remover a guarda `is_ciphered`) e **sabotagem 9** (remover a
dobra de homoglifos) passaram nos 28 testes na primeira tentativa. As duas
guardas existiam e nenhum teste as exercitava — os casos que escrevi eram
resolvidos por caminhos mais rasos.

O conserto foi escrever os testes que faltavam:
- `test_a_mostly_correct_page_is_not_rewritten_to_fix_two_tokens` — vinte
  lances certos e duas manchas, que é a página perigosa de verdade. Sem a
  guarda, o decodificador troca vinte acertos por dois.
- `test_narrowing_to_russian_still_reads_a_latin_k` — a dobra só é
  determinante no caminho estreito; no padrão `K` já é limpo por ser o rei
  inglês, e o teste antigo não provava nada.

Com os testes certos, ambas as sabotagens reprovam. **Sabotagem 10** (alfabeto
só inglês) reprova 15 testes.

### 6.6 Um defeito novo, nomeado e não reivindicado

O livro russo carrega `K` **latino** onde a página imprimiu `К` cirílico.
`Kd2` então parseia como «rei para d2» num livro que disse «cavalo para d2» —
errado, e **silencioso, porque parseia**. É pior que lixo.

Não é esta cifra e este módulo não o conserta: ele apenas se recusa a
reivindicá-lo, para não destruir a única pista que sobrou. O conserto é
normalização de homoglifos mais a reprodução por locale do `legality_repair`.
Entra na §9 como item novo.

---

## 7. A cadeia inteira, medida — 2026-09-11

Três itens desta lista apontavam para o mesmo gargalo: «ninguém liga a
posição do diagrama ao texto do lance». Fui medir, e o gargalo era outro.

### 7.1 O que já estava pronto

Tudo, exceto um elo. O caminho diagrama→FEN roda nesta máquina em **0,55 s por
página** para seis diagramas, com confiança mínima de 0,85 a 1,00
(`caissa.vision.classify` → `chess_diagram_ocr`). A `legality_repair` toma os
lances legais como espaço de candidatos. A §6 inverte a cifra. Só faltava
juntar.

### 7.2 O elo que faltava não era a F2 — era `RegionKind.MOVETEXT`

Juntei, e o repairer recebeu **162 tokens de prosa com lances dentro**:

```
296 Wahls — Ziiger Munich 1989 (296): Although such a 'third rank' defence is
less reliable than the defensive schemes outlined in section 7.1, it is
nevertheless usually enough for a draw: 1 ?c3 Bh6 ...
```

Aceitou **dois lances**, não conseguiu colocar o terceiro, e reportou **sete
idiomas empatados a 0,01 de confiança**. Uma reprodução que elimina leituras
erradas «em dois ou três lances» precisa de dois ou três lances *de lance*.

`RegionKind.MOVETEXT` está na taxonomia desde a F1, tem modo de segmentação
próprio no Tesseract, conta como prosa para a IR — e **nada jamais o
atribuiu**. É um terceiro tipo de cegueira, ao lado dos outros dois que este
relatório já cataloga: não um portão que mede nada, nem um portão apontado para
a unidade errada, mas **uma capacidade declarada e nunca ligada**.

`src/caissa/ocr/notation/movetext.py` a liga.

### 7.3 Duas decisões que a medição forçou

**Análise é uma árvore, não uma linha.** A maior sequência da p140 está **seis
lances dentro** de `(4...g3 5 Qe5+ transposes)`. Reproduzi-la a partir do
diagrama é ilegal por construção, e o repairer aceitou **zero**. Tomando o
tronco: **quatro de quatro**. `move_runs` remove as variantes por padrão.

**Mas o tronco se emenda por cima da variante.** Depois de uma variante a linha
principal retoma **da posição que deixou**, então `1 Qh7+ Kf6 (1...Kg8 2 Qg6+)
2 Qf7+` é a linha contígua `Qh7+ Kf6 Qf7+`. Cada trecho entre parênteses vira
**um** marcador, não um por token — senão a variante longa quebraria o tronco
justamente nas páginas com mais análise. Eu tinha escrito dois testes que se
contradiziam nesse ponto; a semântica do xadrez decidiu qual estava errado.

**Os parênteses vêm desbalanceados do OCR.** Uma guarda global («se não fecha,
não pode») desligava a poda em quase toda página real. O casamento é local, com
teto de 60 tokens: um `(` órfão custa uma lacuna, e apagar o resto da página
custa a página.

### 7.4 O resultado, e ele é modesto

Seis páginas do Nunn, cadeia inteira — diagrama → FEN → Tesseract → cifra →
tronco → legalidade:

| página | lances legais / extraídos | tronco |
|---|---:|---|
| p140 | **5 / 5** | `Qh7+ Sf6! 2 Qf7+ dg5 3 Qe7+` |
| p160 | 4 / 7 | `De6+ Sg6! 2 Bg2+ Hh7! 3 @f8+ …` |
| p240 | 3 / 6 | `1...Gc4 2 Ra7 3 dg2 …` |
| p120, p200, p220 | 0 / 0 | tronco abaixo do piso de 4 lances |

**12 lances legais recuperados de 18 extraídos, em 6 páginas.** É a primeira
vez no projeto que a cadeia inteira produz lance legal a partir de um PDF
digitalizado. Também é pouco, e as três páginas vazias dizem por quê.

### 7.5 O que ainda impede, agora nomeado

1. **Dano residual de token.** `@c2`, `2d2`, `Ef8`, `$g3`: símbolos que não
   limparam o piso de suporte, ou que colidem com letras de peça de algum
   idioma (§6.4). Nas três páginas vazias é isso que derruba o tronco abaixo de
   quatro lances.
2. **`side_to_move` vem de `default` em 6 de 9 diagramas.** Num livro de finais
   metade das posições é das pretas, e o lado errado torna todo lance ilegal a
   partir do primeiro. Testei as duas cores e **não mudou nada** — não é o
   gargalo atual, mas é errado com frequência suficiente para virar um quando
   o resto melhorar.
3. **O tronco não começa necessariamente no diagrama.** O texto sob um diagrama
   às vezes continua uma linha de antes, ou abre por uma variante.

Nada disso é a F2. A F2 continua não iniciada e continua sendo a frente que
falta para processar um livro inteiro — mas **não era ela que impedia a cadeia
de fechar**, e eu disse três vezes que era.

---

## 8. Testes

```
.venv\Scripts\python.exe -m pytest tests\unit\ocr -q
368 passed
```

A frente saiu de 208 para **368** testes; a suíte inteira, de 3.346 para
**3.507**.

| arquivo | testes | o que cobre |
|---|---:|---|
| `test_notation_integrity.py` (novo) | 81 | tokens de oito idiomas, os danos reais do acervo, o alfabeto por construção, e as duas provas de vitalidade |
| `test_movetext.py` (novo) | 18 | o tronco e as variantes, as palavras que a análise intercala, e os parênteses que o OCR perde |
| `test_cipher.py` (novo) | 30 | o decodificador: notação correta em cinco idiomas, os quatro falsos positivos reais, e 18 páginas de corpus intactas |
| `test_page.py` (novo) | 21 | corte por região, espaços de coordenadas, os três caminhos de página inteira, determinismo, e cinco páginas do acervo ponta a ponta |
| `test_text_layer.py` (alterado) | +4 | as tabelas de corpus atualizadas, e o teste que julga se escalar vale a pena — parametrizado para afirmar o contrário no controle |
| `test_arbiter.py` (alterado) | +6 | o repasse do veredito; o adaptador que não o espera; e o termo da palavra fraca, com as duas metades da prova de vitalidade |

**Três testes de corpus mudaram de resposta e a mudança está documentada em
cada docstring**, não escondida: Aagaard p148/p222/p260 e Nunn p120/p200 passam
de 0,98 para 0,55; Gaprindashvili p202/p245 idem. Dvoretsky e Boleslávski,
inalterados, são o controle.

---

## 9. Arquivos

**Criados** — `src/caissa/ocr/notation/` (o pacote estava vazio) com
`cipher.py` e `movetext.py`; `src/caissa/ocr/page.py`;
`tests/unit/ocr/test_notation_integrity.py`, `tests/unit/ocr/test_page.py`,
`tests/unit/ocr/test_cipher.py`,
`tests/unit/ocr/test_movetext.py`;
`benchmarks/notation_integrity.py`, que produz as três tabelas de §2 com um
comando cada (`--what books|sweep|verdicts`, `--json` para gravar e
diferenciar) e lê o acervo local sem que ele **saia desta máquina**
(`CORPUS.md` §0); este relatório.

**Modificados** — `src/caissa/ocr/types.py` (`weak_word_confidence`, §5.2);
`src/caissa/ocr/lexicon.py` (constantes de notação nomeadas,
regex construída a partir delas, figurino Unicode, `is_move_token`,
`is_mangled_move`, `mangled_move_ratio`); `src/caissa/ocr/engines/pdf_text_layer.py`
(três limiares, dois sinais, duas faixas de veredito);
`src/caissa/ocr/arbiter.py` (`RegionTask.verdict`, repassado só quando existe;
`weak_word_quantile` e o quantil no lugar do mínimo, §5.2);
`src/caissa/ocr/page.py` (`_cap_by_page`, §5.1);
`src/caissa/ocr/__init__.py` (exportações);
`tests/unit/ocr/test_text_layer.py` (duas tabelas de corpus, mais o teste de
escalonamento da §4); `tests/unit/ocr/test_arbiter.py` (dois testes do repasse
do veredito); `benchmarks/notation_integrity.py` (o relatório `--what
recovery`); `docs/quality/CORPUS.md` (§0, a contagem de 46; §2, os avisos de
E1 e E2 — ver §7).

**Não tocados** — `src/caissa/core/`, `typeset/`, `notation/`, `vision/`,
`llm/`, `ui/`, `export/`, `index/`, `pyproject.toml`, `scripts/`,
`tests/conftest.py`, e todo o resto de `benchmarks/`.

Fora do produto, também foram atualizados `docs/HANDOFF.md` (o §4.1 vira feito,
uma correção de régua nova na §4.2, o 13.º e o 14.º portões cegos na §7) e
`docs/ROADMAP.md` (a linha da F5, o ciclo de crítica, e o oitavo portão cego).

---

## 10. O que continua faltando

1. ~~`CORPUS.md` precisa de duas correções.~~ **Feito em 2026-09-11.** A §0
   agora diz 46 arquivos e explica a discrepância; a §2 ganhou dois avisos —
   «E1 não implica camada de texto boa», com a tabela dos quatro de cinco que
   falham, e o equivalente para E2. **O único controle nativo do acervo é o
   Dvoretsky**, e agora está escrito lá.
2. ~~Os dezesseis livros danificados não foram reprocessados.~~ **Medido em
   2026-09-11, §4**, e o corretor que aquilo justificou está na §6. Os livros
   em si continuam **não reprocessados**: nada no produto ainda roda o laço
   sobre um livro inteiro e grava o resultado, porque isso é a F2.
3. ~~O laço ainda não rodou com o Tesseract de verdade.~~ **Rodou em
   2026-09-11 — e achou os dois defeitos da §5.** O que fica no lugar disso é
   maior: **o piso de calibração do Tesseract precisa ser ajustado contra o
   corpus rotulado da SPEC §11.2.** Enquanto não for, o nível 0 vence toda vez
   que produz qualquer texto, e os níveis 2 e 3, se instalados, herdam o mesmo
   problema. Está pinado em
   `test_the_cascade_past_level_zero_is_currently_decorative`.
4. ~~O corretor de substituição é o caminho mais curto para valor real.~~
   **Construído em 2026-09-11, §6**, e **ligado à posição no mesmo dia, §7.**
   O que eu chamei aqui de «o outro lado da ponte» e atribuí à F2 era, medido,
   `RegionKind.MOVETEXT`. Fica aberto o que a §7.5 lista: dano residual de
   token, `side_to_move` vindo de `default` em 6 de 9 diagramas, e o tronco
   nem sempre começar no diagrama. **A F2 segue não iniciada** e segue sendo o
   que falta para processar um livro inteiro — mas não é o que impedia a
   cadeia de fechar, e eu disse três vezes que era.
5. **Homoglifo cirílico↔latino é um defeito à parte, agora nomeado** (§6.6).
   `Kd2` num livro russo parseia como «rei d2» e significa «cavalo d2»: errado
   e silencioso. O corretor de cifra se recusa a reivindicá-lo; o conserto é
   normalização de homoglifos mais a reprodução por locale.
6. **Dano que insere um separador escapa.** `♗b5` virando `i.b5` vira três
   tokens, um dos quais é o lance perfeitamente bom `b5`. O índice
   **sub-relata** o dano — direção segura para um sinal que rebaixa confiança,
   mas é uma perda real e está pinada em
   `test_damage_that_splits_a_token_is_a_known_miss`.
7. Os itens 2 a 8 de `F5_REPORT.md` §5 seguem abertos, sem alteração.
