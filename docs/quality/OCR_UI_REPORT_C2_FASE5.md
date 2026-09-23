# OCR/UI · ciclo 2 — relatório do construtor (fase 5: o texto que some sem aviso, a tabela lida por coluna, a janela que não cabe, e a régua do `.pt`)

> **Data:** 2026-09-23 · **Plano:** `docs/OCR_UI_ROADMAP_C2.md` §3d (fase 5: B13, B14, B15, A14,
> C17, C18, A15 — definida nesta sessão a partir do `sol.json` da fase 4 e das dívidas medidas) ·
> **Fases anteriores:** `OCR_UI_REPORT_C2.md`, `…_FASE2.md`, `…_FASE3.md`, `…_FASE4.md` ·
> **Papel:** construtor. Todo número traz o comando ao lado. Ambiente: suíte `.venv` (Python
> 3.11.9), tronco `..\ChessVisionOFF_Puro` (3.10), RTX 5060. O tronco estava no ramo do PR #35
> (`claude/campo-lance-no-resultado`, outra sessão) e voltou a `religa-as-decisoes-orfas`, o ramo
> das fases do ciclo 2, antes de qualquer mudança (o commit do PR continua no ramo dele).
> **Contenção:** as primeiras filas do `bench_sol`, a régua do C17, a suíte do tronco e a checagem
> de população do B14 correram em paralelo nesta máquina; a fila final de A/B (§0.2) correu quase
> sozinha (no meio dela, o arnês do C18 e testes unitários curtos). Os tempos (`s/MP`,
> `s/execução`) desses JSON carregam a contenção e são ditos com ela. O `sol.json` publicado foi
> medido no commit da fase (§A15) — com outra sessão rodando a suíte do tronco ao mesmo tempo: os
> CER e as decisões não dependem de carga (o `f5_before` reproduziu a fase 4, medida sozinha, item
> a item), o `s/MP` depende. Commits: tronco `36d6f65` (código) e `8243e90` (os quatro relatórios de campo
> remedidos); suíte `bb41c55` (código e documentos) e o seguinte (o `sol.json` medido no `bb41c55`, e este relatório fechado). **Outra sessão** trabalhava no tronco durante a integração
> (`qt/janela.py`, `qt/painel_de_texto.py`, `text/rico.py`, `ui/texto_declarado.py` modificados a
> partir das 05:27): não entram nos commits desta fase, e as medições do tronco feitas depois disso
> rodaram numa árvore limpa do commit.

## §0 — Em uma tela (o que o usuário passa a ter)

| antes | depois | portão | passo |
|---|---|---|---|
| uma tabela a 150 DPI e a lista de lances de duas colunas saíam **por coluna** — todos os nomes, depois todos os lugares; todos os lances das brancas, depois os das pretas —, com 100 % dos caracteres certos e CER 0,47–0,68 | os blocos do Tesseract lado a lado cujas linhas casam são lidos **por linha**, dentro da coluna da página e nunca através da calha | `bench_sol`: `scan_degraded_150` CER **0,0224 → 0,0094** — o portão absoluto de 150 DPI do Sol, vermelho desde a fase 1, **verde**; `table:2/4/7` 0,465/0,640/0,676 → 0,0035/0,0036/0; nativos do Dvoretsky 0,590/0,381/0,347 → 0,051/0/0; `two-column` idêntico; 7 itens mudam, nenhum para pior; páginas reais: 28 de 33 idênticas (Levenfis, Estrin, Stefaniu), as outras com a lista de lances por linha ou ruído de diagrama reordenado; sabotagem `table_rows=false` → os números da fase 4 | B13 |
| a leitura que perdia o fim de toda linha, ou linhas inteiras, saía **aceita** (a foto `synth:Dvoretsky…:201:21` aceita a 0,872 com CER 0,786), e as variantes que a leriam não rodavam | a fração das letras da região sob as palavras lidas (`ocr/coverage.py`): abaixo de 0,90 as variantes rodam mesmo com o original aceito, a leitura incompleta não ancora, e nunca sai `ACCEPTED` | aceitos com CER > 0,10 **30 → 7** (nenhum estrato sobe, nenhum entra): 18 lidos inteiros pela variante, 5 para a revisão; `photo` CER **0,0983 → 0,0207**; 27 itens mudam, nenhum para pior; população real (504 regiões de três livros digitalizados) sem alarme falso; piso ajustado só na `calib`; sabotagem `ink_coverage=false` → os 30 | B14 |
| o fax a 0,0382 pelo instrumento honesto da fase 4 | absorvido pelo B14, sem rota própria | `fax_dither` **0,0382 → 0,0249** (≤ 0,0312) | B15 |
| o nível 0, o leiaute por página e o índice de busca liam a camada de texto com as ligaduras (`ﬁ`: 19 nas pp. 6–10 do Polgar) | as bandeiras do PyMuPDF sem `TEXT_PRESERVE_LIGATURES` nos três leitores — a caixa por caractere dividida junto | 19 → **0** nos três; `½ ² №` ficam; sabotagem (bandeiras antigas) → a ligadura volta | A14 |
| a decisão do `.pt` (§10.2) comparava modelos num gate fixo — duas escalas de confiança | a curva risco × cobertura do campo para 15 checkpoints, e o máximo de exatos exportados com ≤ 0/1/2 errados | a produção reproduz o `field_exact` publicado (103 exportados, 102 exatos); sabotagem (rótulos embaralhados sobre as mesmas linhas) → AURC 3–25× pior e a ordem dos modelos a tau +0,20 | C17 |
| com as áreas visitadas e um livro, a janela pedia **1538×659** lógicos — a barra de anotação somava 810 px e uma frase do rodapé pedia 1.246 | rodapé elidido (a frase inteira na dica), barra do campo fluida, os modos da aba Livro e o cartão da Revisão de texto em rolagem | `caissa.ui.audit.minimo`: Clássica 1248×606, Foco **1248×640**, Fita 1246×629 ≤ 1250×640, com e sem livro — PASSOU; sabotagem (rodapé num `QLabel`) → 2206 px, REPROVOU | C18 |
| três invariantes com exceção em todo relatório: `AccentTests` vermelho, `ImpressaoDaMedicaoTests` com `--deselect`, `test_arquitetura` à parte | acentos por posição (nenhuma palavra permitida a mais), a afirmação do arnês num processo novo, os quatro relatórios de campo remedidos no commit | suíte: **4.004 passaram, 0 reprovaram** com o `test_arquitetura` na mesma corrida; tronco numa árvore limpa: 4.781 passaram e o único reprovado é o do ambiente, por construção da árvore efêmera; `ImpressaoDaMedicaoTests` **sem `--deselect`**; `AccentTests` verde | A15 |

### 0.1 O que a medição mudou no desenho (as armadilhas, cada uma medida)

- **Uma fila de A/B com um interruptor novo no meio.** A primeira fila do B13 (`on` e `off`)
  começou com o B14 ainda não escrito; o segundo processo, que nasceria depois de o B14 existir,
  teria o B14 **ligado** do lado `off` — a comparação mediria duas coisas. Parado e refeito: toda
  corrida da fase carrega o `SOL_CONFIG` explícito de **todos** os interruptores da fase
  (`{"table_rows": …, "ink_coverage": …}`), e a fila inteira roda no código final.
- **A semente pequena parte a tabela.** A primeira versão do B13 semeava os grupos na ordem de
  leitura; no `table:4` a 150 DPI as duas células de uma linha só da última fila (`Haia 1937`,
  `Eslava`) formaram um grupo próprio e a linha saiu partida (CER 0,033). Semeando pela coluna de
  células mais alta, 0,0036.
- **O corpus não mostra a página inteira.** Os itens de tabela do corpus são recortes: a regra do
  B13 que passava neles puxou uma coluna para o meio da outra nas páginas inteiras de duas colunas
  do Levenfis (p. 41 com similaridade 0,290 com o desligado). A primeira calha que resolveu isso
  contava **toda** linha da página — e desfez o `table:4` (0,0036 → 0,64), porque nada cruza o vão
  entre as colunas de uma tabela. A regra final conta só prosa; as duas medições vieram antes da
  fila final de A/B (§B13).
- **A altura da Foco não era de quem o comentário dizia.** A rolagem do cartão da Revisão de texto
  veio com um comentário que lhe atribuía os 640 px da Foco; descendo pelo filho mais alto de cada
  nível, quem os segura é a Galeria do tronco (516 px) — a Foco mede 640 antes e depois da rolagem.
  Comentário corrigido, Galeria nomeada (§C18).
- **A cobertura da tinta foi sequestrada duas vezes antes do benchmark** (revisão do próprio
  construtor, com imagens sintéticas — o corpus não tem estes casos, os livros têm): (1) uma foto
  em **meio-tom** (milhares de pontos de 5 px) fez a mediana de altura cair aos pontos e as letras
  virarem «grandes demais» — cobertura 0,009 numa página lida inteira; (2) uma foto de **tom
  contínuo** com manchas do tamanho de letra — 0,64–0,72. Depois: letra medida em polegadas
  (o teto físico do B11, 0,25 pol), tinta só em **linhas** de texto (letras esfregadas duas
  alturas-x na horizontal formando corridas largas, não mais altas que uma linha, e densas) e cada
  letra pesando um — 1,00 nos dois casos, e a leitura que perdeu 3 de 5 linhas continua em 0,40.
  O primeiro A/B do B14 (com a medida ingênua) foi descartado; o piso foi reajustado na `calib`
  com a medida final.
- **A premissa do A14 estava errada pela metade.** A fase 4 escreveu «o texto da camada de texto
  continua com ligaduras»; o extrator do importador (`textlayer._text_flags`) sempre leu com
  `TEXT_PRESERVE_LIGATURES` desligada, e o IR do Polgar já saía limpo. Os que ainda liam com as
  bandeiras padrão eram outros três: o motor de nível 0 (cujo `recognize_page` nem passa pela
  dobra do B12 — 6 ligaduras na p. 6 do Polgar, 5 na p. 9), as linhas de leiaute da página e o
  índice de busca.
- **O mínimo da janela depende de quais áreas já foram visitadas.** A recusa do `capture --escala`
  (fase 4, 1248×695) é medida antes de as áreas serem mostradas; com as áreas visitadas e um
  livro aberto a janela pedia **1538×659**. O motor da largura não era o visor: era a barra de
  anotação sob ele (`PainelDeCampo`, combo + três botões numa `QHBoxLayout`, 810 px na pele Foco);
  e a frase do rodapé num `QLabel` comum pedia 1.246 px sozinha.
- **Um arnês que sai por `os._exit` deixa órfão o processo de trabalho do tronco.** As sondas e o
  arnês do C18 saem sem desmontar a janela (fechar com a leitura do Dataset viva derruba o
  interpretador: `access violation` no `close`, medido); o filho `spawn` do
  `processo_de_trabalho` não morre com o pai no Windows — seis órfãos vivos, e um deles segurou a
  medição seguinte do portão por minutos. O arnês encerra o processo de trabalho (`encerrar(esperar=True)`)
  antes de sair.

### 0.2 Invariantes e portões rodados na integração

| invariante / portão | resultado | comando |
|---|---|---|
| fila final de A/B do `bench_sol` no código final (6 estratos, 747 itens, quatro corridas em sequência, cada uma com o `SOL_CONFIG` dos **dois** interruptores; commit de base `f9ca678` + a árvore da fase) | `f5_on` (os dois ligados), `f5_b13_off`, `f5_b14_off`, `f5_before` (os dois desligados): o `f5_before` reproduz o `sol.json` da fase 4 **item a item** (diferença pareada 0 em todos os estratos e leiautes, os mesmos 30 aceitos errados, os mesmos portões) — os dois interruptores explicam toda a diferença, e o A14 não toca o corpus; 11–13 min por corrida | `scratchpad/bench_f5c.sh` (`CAISSA_FIGURINE_TESSDATA=models\tessdata`, `SOL_CONFIG='{"table_rows": …, "ink_coverage": …}' .venv\Scripts\python.exe benchmarks\bench_sol.py --system sol --strata scan_clean_300,scan_degraded_150,native,shadow_curl_bleed,fax_dither,photo --label <corrida>`); comparação `scratchpad/cmp_f5.py` |
| portões do Sol em `f5_on` | silenciosas **0**, controles **0/9**, ordem **1,0000**, ambiente reproduz; CER 150 DPI **0,0094 ≤ 0,020 ✓** (vermelho desde a fase 1); CER limpo 0,0113, lances 0,9164, inventados 157 — vermelhos (§0.3) | o próprio `bench_sol` |
| B13 em página real (regra final) | Levenfis pp. 36–52, Estrin pp. 20–27, Stefaniu pp. 40–47: **28 de 33** idênticas; as outras 5 com a lista de lances lida por linha ou ruído de diagrama reordenado; nenhum grupo atravessa a calha | `scratchpad/probe_b13_pages.py <pdf> <páginas> ron+eng` com `CAISSA_FIGURINE_TESSDATA` fora do ambiente |
| B14 na população real, pelo importador | 504 regiões medidas em três livros digitalizados, **0** sinalizadas (a menor 0,900) | `scratchpad/b14_population.py`, `b14_population2.py` |
| C17 régua do campo | 15 checkpoints × 3 execuções, linhas idênticas nas três; produção 103/1 no gate = `field_exact`; sabotagem tau +0,20 | `benchmarks\model_ruler.py --runs 3 --tag f5_c17`; `--sabotar embaralhar --linhas-de …` |
| `sol.json` publicado no commit da fase | `bb41c55`, sem `SOL_CONFIG`: 747 itens idênticos aos da `f5_on`; `sol_gate --report-only` sem regressão fora do IC; os três absolutos do §0.3 bloqueados, o de 150 DPI verde (§A15) | `bench_sol … --label sol --publish`; `sol_gate.py --report-only docs\quality\sol\sol.json` |
| C18 mínimo da janela | PASSOU (1248×606 / 1248×640 / 1246×629, com e sem livro); sabotagem REPROVOU (2206) | `caissa.ui.audit.minimo` [`--pdf …1937 Kemeri.pdf`] [`--sabotar rodape`] |
| testes da suíte (com PyQt6, **com** `test_arquitetura.py` na mesma corrida) | **4.004 passaram, 9 pulados, 0 reprovaram** em 998 s (`suite_tests_final.out`; fase 4: 3.931 + 19 à parte) — nenhuma exceção; outra sessão rodava `tests/unit/export` ao mesmo tempo, daí o tempo | `PYTHONPATH=.venv-pack\Lib\site-packages QT_QPA_PLATFORM=offscreen .venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py` |
| testes do tronco (sem `--deselect`, numa árvore limpa do `8243e90`) | **4.781 passaram, 15 pulados, 8 xfail, 1 reprovou** em 523 s (`trunk_tests_final.out`): o reprovado é `test_environment::test_o_pacote_instalado_resolve_para_esta_arvore`, **por construção** na árvore efêmera (ela usa o `.venv` do checkout principal, cuja instalação editável aponta para lá — a mensagem diz isso); os 11 pulados a mais que no checkout principal pedem artefatos fora do git (PDFs, modelos). No checkout principal, `test_environment.py` e `ImpressaoDaMedicaoTests` **17/17** — o `ImpressaoDaMedicaoTests` sem `--deselect` pela primeira vez desde a fase 2. A suíte inteira do tronco não foi rodada no checkout principal para o portão: ele tinha o trabalho em andamento de outra sessão | `cd <árvore> && PYTHONPATH=<árvore>\src QT_QPA_PLATFORM=offscreen ..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider`; no checkout principal `…pytest tests/test_environment.py tests/test_field_eval.py::ImpressaoDaMedicaoTests` |
| `git status --short` | só os caminhos da fase nas duas árvores; fora deles, o trabalho de outras sessões (`packaging/*` e `uv.lock` na suíte; no tronco, `tests/test_qt_resultado_vista_do_impresso.py` e — surgidos durante a integração — `qt/janela.py`, `qt/painel_de_texto.py`, `text/rico.py`, `ui/texto_declarado.py`), não tocado | `git status --short` |

### 0.3 O que ficou vermelho ou aberto (honesto)

- **Três portões absolutos do Sol continuam vermelhos**, os mesmos de toda fase: CER limpo
  0,0113 em 2 estratos (≤ 0,005 — o nativo, 0,0171, é quem puxa), acurácia de lances 0,9164
  (≥ 0,998), 157 lances inventados. O de 150 DPI saiu da lista.
- **Sete aceitos com CER > 0,10 ficaram** (eram 30; nenhum entrou): um nativo do Dvoretsky
  (`20:96:252`, 0,417), quatro de sombra (`Xadrez Vitorioso 156:266` 0,426, `120:398`, `60:324`,
  e o sintético `Dvoretsky 75:4` 0,221), um de fax (`authored:de:1`, 0,139) e um de foto
  (`Dvoretsky 54:1`, 0,105). A cobertura dos seis de raster fica entre 0,93 e 1,00
  (`f5_b14_fit2.json`, medida com o B14 desligado): a leitura cobre a tinta e erra dentro dela — o
  B14 mede o texto que falta, não o texto errado. O nativo tem 12 caracteres, abaixo das 12 letras
  que a medida pede para dizer alguma coisa.
- **A pele Foco fica no teto do portão da janela** (1248×640 ≤ 1250×640), segurada pela Galeria do
  tronco (516 px); a rolagem da Galeria é a próxima alavanca, não tomada (§C18). E a 125 % sobre
  1366×768 a janela continua sem caber — os pisos declarados das duas colunas somam mais que os
  1093 px lógicos (fase 4, inalterado).
- **A folga do piso do B14 é fina em região pequena**: na população real a menor cobertura do
  Stefaniu é 0,900 (cartões de ~20 letras), no piso e não abaixo (§B14).
- **A régua do C17 não decide o `.pt`**: com uma semente por variante, a variância entre sementes é
  maior que a diferença entre variantes (§C17); a troca continua da pessoa (§10.2).
- **O B13 reordena o ruído que o Tesseract lê dentro dos diagramas** das páginas reais (Levenfis
  pp. 36, 39, 40; Estrin p. 20): ruído antes e depois, só em outra ordem.
- **Não tomados, como o §3d disse**: o `18 . . .` do Dvoretsky, os homóglifos `Kp`/`Кр`, o `vazio`
  a 200 %, o alto contraste como pele, a crítica das fases 3 e 4.

## §B13 — A tabela e a lista de lances lidas por linha

- **Arquivos.** Suíte: `ocr/layout/rows.py` (novo: `rows_of_tables`, `table_groups`,
  `TableRowsConfig`), `ocr/arbiter.py` (`ArbiterConfig.table_rows`; aplicado ao resultado de todo
  motor em PSM 1/3 — o de segmentação própria —, antes do escore), `ingest/pdf/ocr_service.py`
  (`OcrServiceConfig.table_rows`, levado ao árbitro da página e das variantes),
  `tests/unit/ocr/test_table_rows.py` (novo, 16). O `bench_sol` já entrega o `SOL_CONFIG` inteiro
  ao `OcrServiceConfig`: nenhuma linha nova lá.
- **A regra** (a docstring de `rows.py` tem os números e a razão de cada um): blocos **lado a lado**
  (`x` disjuntos, `y` sobrepostos); o grupo nasce num bloco de **células** — linha mediana de até
  12 caracteres (a constante do RapidOCR) **e nenhuma linha acima de 24**, ou calha interna nas
  próprias linhas —, a coluna de células mais alta primeiro; cresce pelo vizinho cujas linhas
  acham par de altura no grupo em ≥ 80 % das vezes; bloco de prosa (≥ 3 linhas, mediana ≥ 30, sem
  calha) nunca entra; e **o grupo não cruza a calha da página**. O grupo sai linha a linha, cada
  linha da esquerda para a direita, no lugar do primeiro bloco.
- **Duas regras que o corpus não pedia e a página real pediu.** Os itens de tabela do corpus são
  recortes. Na página inteira, a primeira versão puxou uma coluna para o meio da outra no Levenfis
  (1962, digitalizado, duas colunas): p. 40 com similaridade **0,857** com o desligado, p. 41
  **0,290** (`scratchpad/probe_b13_pages.py`, `difflib` sobre o texto final da página com
  `table_rows` ligado e desligado). Duas causas, cada uma rastreada bloco a bloco
  (`probe_b13_trace.py`): o bloco da coluna direita (lances curtos **e** uma linha de prosa,
  «Scopul a fost atins, tempoul a», com calha interna dos números de lance) valia como coluna de
  células e semeou; e o ruído que o Tesseract lê num diagrama da coluna esquerda semeou um grupo
  que atravessou a calha. Daí o teto de 24 caracteres por linha de célula, e a calha: **um
  corredor de ≥ 8 px dentro do vão que no máximo 10 % das linhas de prosa (≥ 30 caracteres) que
  alcançam os dois blocos tocam**, julgado com ≥ 8 dessas linhas. Um corredor, não o vão inteiro:
  o fragmento da lista da esquerda acaba antes da margem da coluna, e o vão até o bloco da direita
  começa dentro da prosa da esquerda (medido: 790–888, prosa até 800). **Só prosa conta:** a
  primeira versão contava toda linha e desfez o `table:4` a 150 DPI (18 linhas, e nada cruza o vão
  entre as colunas de uma tabela: **0,0036 → 0,64**, medido) — travado por
  `test_a_table_s_own_column_gaps_are_not_a_gutter`, cuja fixture é a leitura do produto; com a
  contagem antiga o grupo some (conferido).
- **Página real, regra final** (`probe_b13_pages.py`, `table_rows` ligado × desligado, sem o
  B14, `CAISSA_FIGURINE_TESSDATA` fora do ambiente): **Levenfis pp. 36–52** — 13 de 17
  idênticas, p. 41 idêntica (era 0,290), p. 40 0,981 e p. 50 0,999 com a lista de lances lida por
  linha (`2. Re7—b7 De5—a5`, `3. Rb7—c8! Da5—a8-+`, `3. Nb3—c2-+- Rg6—g5`, antes um lance por
  linha, o branco longe do preto), pp. 36 e 39 só com o ruído lido dentro de um diagrama
  reordenado (`// a mm`); **Estrin pp. 20–27** — 7 de 8 idênticas, a p. 20 só com ruído de
  diagrama; **Stefaniu pp. 40–47** — 8 de 8 idênticas. Nenhum grupo atravessa a calha (os grupos
  da p. 40, rastreados: a lista da esquerda, a da direita e o ruído de um diagrama).
- **Corpus, item a item** (`scratchpad/probe_table.py`, serviço de produção,
  `SOL_CONFIG={"table_rows": false|true, "ink_coverage": false}`): `table:2` 0,465 → **0,0035**,
  `table:4` 0,640 → **0,0036**, `table:7` 0,676 → **0**, a 150 DPI; os três nativos do
  Dvoretsky `17:401:52` 0,590 → **0,051**, `11:54:52` 0,381 → **0**, `13:278:52` 0,347 → **0**;
  as três tabelas a 300 DPI ficam em 0 dos dois lados.
- **Portão: PASSOU** (`bench_sol`, seis estratos, 747 itens; `f5_on_20260923_045448.json` ×
  `f5_b13_off_20260923_050724.json`, o B14 ligado nos dois; diferença pareada item a item com IC
  95 % bootstrap, `scratchpad/cmp_f5.py`):

  | | desligado | ligado | diferença pareada [IC 95 %] |
  |---|--:|--:|---|
  | `scan_degraded_150` CER | 0,0224 | **0,0094** (portão ≤ 0,020) | −0,0129 [−0,0308; 0,0000] |
  | `native` CER | 0,0235 | **0,0171** | −0,0054 [−0,0121; −0,0001] |
  | leiaute `table` (12 itens) | 0,1517 | **0,0038** | −0,1478 [−0,2718; −0,0385] |
  | leiaute `two-column` (52) | 0,0111 | 0,0111 | 0 (idênticos) |
  | leiaute `single` (666) | 0,0199 | 0,0179 | −0,0019 [−0,0046; −0,0000] |
  | `scan_clean_300`, `photo`, `fax_dither`, `shadow_curl_bleed` | — | — | 0 (idênticos) |

  (O IC do 150 DPI toca o zero porque só 3 dos 137 itens mudam — as três tabelas —, todos no
  mesmo sentido.) Nos 747 itens o B13 muda **7**, e nenhum para pior: as três tabelas a 150 DPI e
  quatro listas nativas do Dvoretsky (`17:401:52`, `11:54:52`, `13:278:52` e `20:396:53`, 0,095 →
  0,081). O portão absoluto de 150 DPI do Sol, vermelho desde a fase 1, **fica verde**; `table:2/4/7`
  ≤ 0,05 (0,0035/0,0036/0); os três nativos do Dvoretsky < 0,15 (0,051/0/0); `two-column` e
  `single` sem regressão; ordem de leitura 1,0000; silenciosas 0; controles 0/9. A acurácia de
  lances não muda (0,8817 a 150 DPI, 0,9416 no nativo): ela conta os lances, não a ordem deles —
  o que o B13 conserta é o texto que a pessoa lê.
- **Sabotagem.** `SOL_CONFIG='{"table_rows": false, "ink_coverage": true}'` devolve os números da
  fase 4 nos estratos que o B14 não toca, ao décimo de milésimo (150 DPI 0,0224, nativo 0,0235,
  `scan_clean_300` 0,0054; os seis itens com o CER da fase 4). Nos testes: duas colunas de prosa de
  linhas alinhadas → nenhum grupo; sem o teto de 24 **e** sem a calha, o bloco da coluna direita da
  p. 40 semeia e puxa a esquerda (cada regra sozinha o segura); sem a calha, duas colunas de
  células atravessam a calha da página.

## §B14 — A leitura que não cobre a tinta não é aceita, e a variante roda

- **Arquivos.** Suíte: `ocr/coverage.py` (novo: `ink_map(gray, dpi)` → `InkMap`, `ink_coverage(result,
  ink)`), `ingest/pdf/ocr_service.py` (`OcrServiceConfig.ink_coverage`, `min_ink_coverage=0.90`;
  `RegionRecognition.ink_coverage`; em `_wants_variants` a leitura incompleta pede as variantes
  mesmo aceita; em `_settle` a incompleta não ancora quando há uma completa e nenhuma incompleta sai
  `ACCEPTED`), `ocr/fusion.py` (`fuse_candidates(incomplete=…)`: a âncora prefere a leitura
  completa), `benchmarks/fit_ink_coverage.py` (novo: o piso ajustado **só na `calib`**, a `dev`
  impressa ao lado), `ocr/gates.py` e `benchmarks/bench_sol.py` («aceitos errados» — aceitos com
  CER > 0,10 — no resumo de cada estrato e no `sol.md`), `tests/unit/ocr/test_ink_coverage.py`
  (novo, 17), `tests/unit/ocr/test_sol_metrics.py` (+1).
- **A medida** (os números e a razão de cada um estão em `CoverageConfig`): o fundo estimado por
  fechamento morfológico (0,2 pol), tinta abaixo de 0,62 do fundo; **letra** é o componente de
  0,03–0,25 pol de altura (o teto físico do B11), razão de aspecto ≤ 25; as letras esfregadas duas
  alturas-x na horizontal formam corridas, e só a corrida que é **linha de texto** conta (razão de
  aspecto ≥ 3, altura ≤ 3,5× a mediana — as linhas reais da foto medem 2,2–2,9× —, ≥ 0,4 letra
  por altura de linha); coisas maiores que 4× a mediana (fotos, molduras) e as caixas de diagrama
  que o chamador passa (`page_context`) ficam fora; cada letra pesa um. A cobertura é a fração das
  letras sob as caixas de palavra (com 0,35 da altura de folga); com menos de 12 letras, nenhuma
  palavra (`None`). Uma passada por página: **142–229 ms** numa página de 300 DPI com a máquina
  ocupada (`scratchpad/probe_b14.py`).
- **O piso, ajustado na `calib`** (`benchmarks/fit_ink_coverage.py --out
  benchmarks/reports/sol/f5_b14_fit2.json`, serviço **sem** o B14, a cobertura mínima das regiões de
  cada leitura; «perdida» = CER > 0,10, «boa» = CER ≤ 0,02):

  | piso | `calib` sinaliza | perdidas | boas | aceitas-perdidas | `dev` sinaliza | perdidas | boas | aceitas-perdidas |
  |---|--:|--:|--:|--:|--:|--:|--:|--:|
  | 0,80 | 1 | 1/16 | 0/182 | 1/8 | 6 | 6/30 | 0/359 | 4/21 |
  | 0,85 | 3 | 3/16 | 0/182 | 3/8 | 15 | 15/30 | 0/359 | 11/21 |
  | 0,88 | 6 | 6/16 | 0/182 | 6/8 | 19 | 19/30 | 0/359 | 15/21 |
  | **0,90** | **6** | **6/16** | **0/182** | **6/8** | 21 | 21/30 | 0/359 | 17/21 |
  | 0,92 | 7 | 7/16 | 0/182 | 6/8 | 21 | 21/30 | 0/359 | 17/21 |
  | 0,96 | 10 | 8/16 | 0/182 | 6/8 | 24 | 23/30 | 0/359 | 19/21 |

  A regra, dita antes de olhar a `dev`: o piso que sinaliza o máximo de aceitas-perdidas da `calib`
  sem sinalizar uma boa. A `calib` não separa os pisos de (0,8756; 0,9000] — todos sinalizam as
  mesmas seis leituras (a sétima está em 0,9000 exatos) —, e 0,90, o do primeiro ajuste, está no
  intervalo: fica. A `dev` só confere: 17 das 21 aceitas-perdidas e nenhuma das 359 boas.
- **Na população real, pelo importador** (`scratchpad/b14_population.py`/`b14_population2.py`: o
  `import_pdf` de verdade, com o localizador de diagramas passando as caixas ao serviço, e um
  `OcrService` que grava a cobertura de toda região): Estrin pp. 20–27 (80 regiões medidas, a menor
  0,969), Levenfis pp. 40–51 (240, a menor 0,931), Stefaniu pp. 40–51 (184, a menor **0,900**) —
  **nenhuma** das 504 sinalizada; Kemeri, Neumann e Boleslavski têm camada de texto (o B14 não se
  aplica: 0 regiões de raster). **A folga é fina em região pequena:** as menores do Stefaniu são
  cartões de ~20 letras, onde duas letras fora já dão 0,90 — no piso, não abaixo. Se o campo
  mostrar revisão demais nessas, a alavanca é um mínimo de letras perdidas (uma palavra), não o piso.
- **Portão: PASSOU** (`f5_on_20260923_045448.json` × `f5_b14_off_20260923_051900.json`, o B13
  ligado nos dois; `scratchpad/cmp_f5.py`):

  | estrato | CER desligado | CER ligado | diferença pareada [IC 95 %] | aceitos errados | revisão | s/MP* |
  |---|--:|--:|---|--:|--:|--:|
  | `photo` | 0,0983 | **0,0207** | −0,0776 [−0,1113; −0,0488] | 20 → **1** | 16 → 17 | 6,93 → 8,51 |
  | `fax_dither` | 0,0382 | **0,0249** | −0,0133 [−0,0258; −0,0029] | 4 → 1 | 19 → 21 | 5,40 → 5,51 |
  | `shadow_curl_bleed` | 0,0377 | 0,0359 | −0,0017 [−0,0051; 0,0000] | 5 → 4 | 27 → 28 | 6,06 → 5,93 |
  | `native`, `scan_clean_300`, `scan_degraded_150` | — | — | 0 (idênticos) | 1 → 1, 0, 0 | = | ≈ |

  **Aceitos com CER > 0,10: 30 → 7**, nenhum estrato sobe e nenhum entrou. Dos 30: **18** saem
  aceitos e certos (a variante que o B14 pediu leu o texto inteiro: CER mediano 0,0039, máximo
  0,0296 — `authored:de:4` 0,230 → 0, `authored:es:8` 0,266 → 0, `synth:Xadrez Vitorioso…:131:52`
  0,243 → 0,013), **5** vão para a revisão também com o texto bem melhor
  (`synth:Dvoretsky…:201:21` 0,786 → 0,007, `authored:en:21` 0,204 → 0,028), **7** ficam (§0.3). Nos
  747 itens o B14 muda 27, **nenhum para pior**; uma leitura em revisão passa a aceita
  (`authored:pt:18@photo` 0,29 → 0). Silenciosas 0, controles 0/9. *O `s/MP` destes JSON carrega a
  contenção da máquina (§ cabeçalho): a foto paga as variantes (+23 % nesta comparação, entre
  corridas de contenção parecida).
- **Sabotagem.** `SOL_CONFIG='{"table_rows": true, "ink_coverage": false}'` devolve os 30 e os
  números da fase 4 nos três estratos que o B14 toca, ao décimo de milésimo (foto 0,0983, fax
  0,0382, sombra 0,0377). Nos testes (`test_the_sabotage_switch_accepts_the_partial_reading_again`):
  com o interruptor desligado a leitura que perdeu as últimas linhas volta a sair `ACCEPTED`.

## §B15 — O fax, depois do B14

- **Absorvido pelo B14, sem código próprio.** O §3d mandava medir o fax depois do B14 e só entrar
  com a rota do pontilhado (upscale + segundo motor) se o número não viesse. Veio: `fax_dither`
  **0,0382 → 0,0249** com o B14 (diferença pareada −0,0133 [−0,0258; −0,0029], fora do IC), abaixo
  do alvo de 0,0312 que a fase 4 tinha nomeado — e o B13 não toca o fax (idêntico ligado ou
  desligado). O `authored:en:21`, que a fase 4 citou como a linha inteira perdida (cobertura 0,847),
  sai 0,204 → 0,028; dos 4 aceitos errados do fax fica 1 (`authored:de:1`, 0,139, cobertura 0,964:
  erra dentro da tinta que leu). Acurácia de lances do fax 0,8201 → 0,8505.
- **Portão: PASSOU** (`fax_dither` ≤ 0,0312). **Sabotagem:** a do passo que entrou — o B14
  desligado devolve 0,0382.

## §A14 — As ligaduras da camada de texto

- **Arquivos.** Suíte: `ocr/engines/normalize.py` (`text_layer_flags(mode)`: as bandeiras padrão
  do PyMuPDF para o modo **sem** `TEXT_PRESERVE_LIGATURES` — nada mais muda), `ocr/engines/
  pdf_text_layer.py` (as cinco leituras da camada: `text`, `dict` ×2, `rawdict`), `ocr/layout/
  analyze.lines_from_pdf_page`, `index/sources.PdfTextSource.units`,
  `tests/unit/ocr/test_text_layer_ligatures.py` (novo, 6).
- **Por que as bandeiras e não o `fold_result`.** O MuPDF, com a bandeira desligada, divide a
  ligadura nas letras **e a caixa entre elas** (`ﬁ` → `f` com a caixa, `i` com largura zero no fim):
  o nível 0 é a leitura que guarda caixa por caractere (`rawdict`), e trocar o texto da palavra sem
  trocar os caracteres deixaria `char_box(offset)` apontando para a letra errada. O teste confere
  `len(word.chars) == len(word.text)`.
- **Portão.** Polgar, páginas 6–10 (índices 5–9), as 19 ligaduras que `page.get_text("text")`
  devolve com as bandeiras padrão: **0** no nível 0 (`recognize_page(force=True)`), **0** nas
  linhas de leiaute, **0** no índice de busca (`PdfTextSource(max_pages=10)`); `½`, `²`, `№`
  ficam. **Sabotagem:** as bandeiras antigas no nível 0 (`monkeypatch` de `text_layer_flags`) →
  a ligadura volta (`test_the_sabotage_old_flags_bring_the_ligature_back`). O IR do importador já
  saía com 0 — a correção vale para o que lê a camada por fora do importador: o OCR de contestação
  (onde o nível 0 ancora regiões), o leiaute por página e a busca.

## §C17 — A régua do campo para a decisão do `.pt` (§10.2)

- **Arquivos.** Tronco: `field_eval.py` (`FieldReport.diagrams`: uma linha por diagrama casado —
  livro, página, índice, `legal`, `gate_confidence`, `min_confidence`, `exact` na régua anotada,
  `contaminated` —, somada por `_accumulate`, fora do `as_dict` para não inchar os relatórios
  publicados), `tests/test_field_eval.py` (+1: as linhas refazem o gate em qualquer limiar).
  Suíte: `benchmarks/field_exact.py` (leva as linhas adiante), `benchmarks/model_ruler.py` (novo),
  `tests/unit/classify/test_model_ruler.py` (novo, 8).
- **Medição** (`benchmarks/model_ruler.py --runs 3 --tag f5_c17`, régua corrigida do
  `field_exact`, recall do pacote de produção, sem motor UCI; cada modelo três vezes, as linhas por
  diagrama **idênticas** nas três — o harness recusa se não forem; 51–103 s por execução, com a
  máquina ocupada pela fila do B13/B14): `benchmarks/reports/model_ruler_20260923_043817_f5_c17.json`.
  114 diagramas casados e julgáveis por modelo. «≤ k err» é o maior número de diagramas **exatos**
  exportados com no máximo k errados, e o limiar do gate que o consegue:

  | modelo | exatos | gate 0,80: exp / err | ≤ 0 err | ≤ 1 err | ≤ 2 err | AURC |
  |---|---:|---:|---:|---:|---:|---:|
  | **produção** | 107 | **103 / 1** | 0 | 103 (0,50) | 103 (0,37) | 0,0063 |
  | `c4_aug0_s42` | 105 | 104 / 2 | 75 (0,99) | 97 (0,93) | 104 (0,62) | 0,0070 |
  | `c4_aug0_s43` | 104 | 102 / 2 | 96 (0,91) | 97 (0,86) | 102 (0,74) | 0,0056 |
  | `c4_aug0_s44` | 110 | 101 / 0 | 104 (0,67) | 105 (0,64) | 110 (0,30) | 0,0017 |
  | `c4_mhsp_s42` | 106 | 105 / 1 | 103 (0,84) | 104 (0,76) | 105 (0,52) | 0,0036 |
  | `c4_mhsp_s43` | 102 | 104 / 3 | 0 | 99 (0,88) | 99 (0,85) | 0,0126 |
  | `c4_mhsp_s44` | 105 | 86 / 0 | 91 (0,72) | 92 (0,63) | 103 (0,50) | 0,0063 |
  | `c4_mhspe_s42` | 102 | 102 / 3 | 99 (0,87) | 99 (0,81) | 99 (0,81) | 0,0077 |
  | `c4_mhspe_s43` | 102 | 98 / 4 | 0 | 87 (0,95) | 89 (0,90) | 0,0181 |
  | `c4_mhspe_s44` | 104 | 102 / 2 | 0 | 100 (0,87) | 104 (0,59) | 0,0112 |
  | `c4_e_s42` | 108 | 100 / 2 | 96 (0,90) | 96 (0,88) | 102 (0,63) | 0,0051 |
  | `c4_e_s43` | 107 | 98 / 2 | 0 | 95 (0,83) | 103 (0,54) | 0,0138 |
  | `c4_e_s44` | 109 | 100 / 1 | 0 | 101 (0,64) | 108 (0,30) | 0,0136 |
  | `c4_x10_s42` | 108 | 72 / 0 | 93 (0,67) | 101 (0,55) | 101 (0,53) | 0,0042 |
  | `c4_w3_s42` | 109 | 104 / 2 | 78 (0,99) | 99 (0,88) | 106 (0,53) | 0,0052 |

- **Portão: PASSOU.** No gate 0,80 a produção exporta **103 com 1 errado — 102/103**, o número do
  `field_exact` publicado. **Sabotagem** (`--sabotar embaralhar --linhas-de …_f5_c17.json`: os
  rótulos de exatidão redistribuídos com semente fixa sobre as **mesmas** linhas, sem medir o campo
  de novo; `model_ruler_20260923_044211_f5_c17_sabotado.json`): o AURC de todo modelo piora de 3,4
  a 25× (produção 0,0063 → 0,0727), as três colunas «≤ k err» caem a 0 em 11 dos 15, e a ordem dos
  modelos pelo AURC fica com **tau de Kendall +0,20** contra a verdadeira — a régua lê a verdade,
  não as confianças. Nos testes, a mesma sabotagem sobre dois modelos construídos.
- **O que a régua diz para §10.2** (a troca continua da pessoa). (1) O único errado que a produção
  exporta é o diagrama **mais confiante** dela (Burgess p. 60 d2, 0,998): nenhum limiar exporta
  com zero erros — por isso a coluna «≤ 0» é 0. (2) Com o mesmo risco de um errado, a produção
  entrega 103; `c4_aug0_s44` 105, `c4_mhsp_s42` 104 — **uma semente cada**: as outras duas sementes
  das mesmas variantes entregam 96–97 e 99. A variância entre sementes é maior que a diferença
  entre variantes, o mesmo veredito da fase 3 (§C4) agora na régua do dano. (3) O `x10` (ruído de
  rótulo) exporta 72 no gate, mas **não** é pior na curva: 93 exatos com zero errados — é outra
  escala, como a fase 4 suspeitou. Nada a trocar com uma semente; o que decidiria é a mesma curva
  com três sementes da variante escolhida contra a produção retreinada nas mesmas três.

## §C18 — A janela cabe no portátil

- **Arquivos.** Tronco: `qt/rodape.py` (a mensagem, os dispositivos e a ocupação em
  `RotuloElidido` — a frase inteira na dica e em `mensagem()`/`dispositivos()`), `qt/campo.py` (a
  barra de anotação numa `BarraFluida`, a mesma da barra do visor: os botões descem de linha em vez
  de somar), `qt/painel_principal.py` (cada modo da aba Livro dentro de uma rolagem vertical, a API
  devolvendo o painel de dentro), `tests/test_qt_janela_cabe.py` (novo, 8). Suíte:
  `ui/widgets/rotulo_que_encolhe.py` (novo: pinta elidido, `text()` continua inteiro, mínimo zero),
  `ui/views/rotulagem.py` e `ui/widgets/cartao_da_linha.py` (os rótulos de estado e de contexto),
  `ui/views/revisao_de_texto.py` (o cartão numa rolagem vertical), `ui/audit/minimo.py` (novo: o
  portão), `tests/unit/ui/test_rotulo_que_encolhe.py` (novo, 4).
- **Onde estava o mínimo, medido** (pele Foco, áreas visitadas, livro aberto; `scratchpad/
  probe_chain.py`, `probe_minsize2.py`): o divisor somava as abas (piso declarado 540) + o lado do
  visor **992** — o visor (520) empilhado com a barra de anotação (**810**: combo 198 + botões 178
  + 166 + 250 + vãos) mais o trilho (176); o rodapé pedia **1.246** com a frase de importação no
  `QLabel` da mensagem; na altura, o modo mais alto da aba Livro (o Resultado, **520**). Fora do
  mínimo da janela, mas cortando o conteúdo das abas: a linha de estado da Rotulagem pedia
  **2.868** px e o contexto do cartão, **1.056**.
- **Portão** (`caissa.ui.audit.minimo`: um subprocesso por pele, áreas visitadas, frase de 300
  caracteres no rodapé, teto 1250×640; `docs/quality/ui/c2_fase5/minimo_20260923_074522.json` sem
  livro e `…_074539.json` com o Kemeri, cópias dos de `benchmarks/reports/ui/c2_fase5/minimo/`): **PASSOU** —
  Clássica **1248×606**, Foco **1248×640**, Fita **1246×629**, idênticos com e sem livro.
  **Sabotagem** (`--sabotar rodape`: a mensagem num `QLabel` comum) → **2206×606 / 2206×640 /
  2194×629, REPROVOU** nas três peles (`minimo_sabotado_rodape_20260923_074552.json`).
- **A Foco fica no teto, e quem a segura é a Galeria do tronco.** Descendo pelo filho mais alto de
  cada nível (`scratchpad/probe_altura.py`): a pilha de áreas pede 516 px, e a página que pede 516
  é o `PainelDaGaleria` (Dataset 317, Rotulagem 266, Revisão de texto 135, Livro 91); a Foco soma
  124 px de cromo a isso, a Clássica 90. O cartão da Revisão de texto, que esta fase pôs numa
  rolagem, pedia 501 — **abaixo** da Galeria: a rolagem não baixou o mínimo de hoje (o comentário
  que a primeira versão escreveu dizendo o contrário foi corrigido); ela impede que a Revisão de
  texto passe a decidir quando a Galeria deixar. A Galeria na rolagem é a próxima alavanca e não foi
  tomada: a página da aba é o painel, e a janela e o arnês da suíte o procuram por identidade
  (`indexOf`, `widget(i)`, `area_atual`) — mudar isso é passo, não remendo.
- **O que não muda e por quê.** A 125 % sobre 1366×768 (1093×582 lógicos) a janela continua sem
  caber: os pisos **declarados** das duas colunas (abas 540 = recorte 240 + lateral 260 + folga;
  visor 520) já somam mais que 1093, e mudá-los é desenho — o número fica dito para o crítico C3.

## §A15 — As invariantes num comando só

- **`test_strings::AccentTests` (tronco), vermelho desde a fase 2.** Os seis achados eram todos
  identificadores: o id de comando `Comando("configuracoes", "Configurações…", …)` e o
  `Item("configuracoes")` do menu, a chave do despacho `"configuracoes": lambda…`, a chave do JSON
  gravado em disco (`{"pagina": …}`, `item["pagina"]`), o token cujo valor é o próprio nome
  (`SELECAO = "SELECAO"`) e a lista de palavras **dobradas** do casamento de títulos
  (`"… quebra cabecas …".split()`). A régua ganhou regras **por posição** — chave de dicionário e
  de subscrito, primeiro argumento de `Comando`/`Item`, o literal igual ao nome em maiúsculas, o
  receptor de `.split()` —, só para literais com forma de identificador nas três primeiras; nenhuma
  palavra entrou em `PERMITIDOS`. **Sabotagem/anti-brecha:**
  `test_os_identificadores_escapam_e_o_texto_de_tela_nas_mesmas_posicoes_nao` — `{"Pagina
  seguinte": …}`, `Comando("abrir", "Configuracoes da pagina")`, `{"pagina": "Ir para a pagina"}` e
  `QLabel("pagina")` continuam varridos.
- **`test_arquitetura` (suíte), «à parte» em todo relatório.** A afirmação «importar o arnês não
  traz um binding de Qt» agora roda num **processo novo** por arnês; com um teste de janela antes
  na mesma corrida continua verde (23/23 com `test_importacao_view.py` primeiro).
  **Sabotagem:** um pacote temporário com `from PyQt6 import QtCore` no topo → o subprocesso
  devolve 1 e o nome do binding (`test_a_sabotagem_um_qt_no_topo_do_arnes_reprova`).
- **`ImpressaoDaMedicaoTests` (tronco), `--deselect` em toda fase.** O teste compara o digest dos
  módulos do caminho de medição gravado em cada relatório corrente com o de hoje; os quatro
  (`field_20260822_s99`, `controle_20260822`, `mhsp_20260822`, `s108_20260822`) tinham sido
  medidos no `7bcb396` (F9-C12) e dezoito módulos se moveram desde então — o `field_eval` desta
  fase entre eles. Remedidos pelo mesmo procedimento da F9-C12: uma árvore **limpa e efêmera** do
  commit da fase no tronco (`git worktree add --detach`), os quatro `.pt` copiados para dentro dela
  (o caminho gravado sai relativo, e o `.gitignore` não os deixa sujar a árvore), os PDFs lidos do
  checkout principal (o caminho não é gravado) e a saída **fora** da árvore — gravar em
  `docs/metrics` dentro dela a sujaria para a medição seguinte (`scratchpad/remedir_campo.sh`).
  Os quatro gravam `commit 36d6f654`, `dirty=false`, o `.pt` em caminho relativo e nenhum caminho
  absoluto (tronco `8243e90`). **Não é reprodução, é medição nova** — os quatro mudaram, e na
  mesma direção, porque a detecção mudou desde o `7bcb396`:

  | relatório (modelo) | casados | falsos positivos | exportados | taxa de exportação | exportados errados | exatidão de campo | exatos |
  |---|--:|--:|--:|--:|--:|--:|--:|
  | `field_20260822_s99` (produção) | 109 → 114 | 3 → 0 | 100 → 103 | 0,8696 → **0,8957** | 2 → 3 | 0,9787 → 0,9709 | 93 → 103 |
  | `controle_20260822` | 109 → 114 | 3 → 0 | 91 → 93 | 0,7913 → **0,8087** | 0 → 0 | 1,0000 → 1,0000 | 89 → 94 |
  | `mhsp_20260822` | 109 → 114 | 3 → 0 | 84 → 86 | 0,7304 → **0,7478** | 1 → 1 | 0,9878 → 0,9884 | 85 → 90 |
  | `s108_20260822` | 109 → 114 | 3 → 0 | 86 → 88 | 0,7478 → **0,7652** | 1 → 1 | 0,9880 → 0,9886 | 91 → 100 |

  Os três exportados errados da produção, pela régua **anotada** do tronco: Euwe p. 40, Burgess
  p. 60 (o de 0,998 do §C17) e Niemeijer p. 20 — este último é a anotação errada que a fase 4 achou
  (`field_corrections.json`); pela régua corrigida da suíte são 102/103, o número do §C17. A
  oitava remedição entrou no registro das anteriores (`docs/SPEC_REVISAO.md` do tronco). Com eles,
  `ImpressaoDaMedicaoTests` passa **sem `--deselect`** (§0.2).
- **`sol.json` no commit.** `docs/quality/sol/sol.json`/`.md` republicados sobre o **`bb41c55`** — o
  `environment.commit` do JSON é o do commit da fase pela primeira vez (o da fase 4 gravava o
  `f3bd27e`, a árvore anterior ao commit), sem `SOL_CONFIG` (os padrões de produção: os dois
  interruptores ligados). Os 747 itens saem **idênticos** aos da `f5_on` em CER e decisão; aceitos
  errados 7; o `sol.md` ganha a coluna. `sol_gate --report-only`: silenciosas 0, controles 0/9,
  ordem 1,0000, nenhuma regressão de CER fora do IC contra o `baseline`; bloqueados os mesmos três
  absolutos do §0.3 (o de 150 DPI verde). O `s/MP` publicado carrega a suíte do tronco que outra
  sessão rodava ao mesmo tempo (`scan_clean_300`, que o B13 e o B14 não mudam, 1,33 → 1,48: ~11 %
  de contenção; a foto 7,19 → 9,55 soma a contenção e as variantes do B14). Comando:
  `CAISSA_FIGURINE_TESSDATA=models	essdata .venv\Scripts\python.exe benchmarksench_sol.py --system sol
  --strata scan_clean_300,scan_degraded_150,native,shadow_curl_bleed,fax_dither,photo --label sol
  --publish`, e `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json`.
