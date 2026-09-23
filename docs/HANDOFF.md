# Handoff — estado em 2026-09-11 (atualizado no ciclo F2-C1)

> Documento de passagem. Diz **onde o trabalho está**, **o que ler**, **o que fazer a
> seguir** e **o que não refazer**. Escrito para quem chega sem o contexto da conversa.

---

## 1. Em uma tela

Caïssa Studio é a unificação de cinco projetos que já existiam em `C:\Python-Chess2\`.
**Não é um projeto novo** — ver `docs/ASSETS.md` antes de escrever qualquer linha.

| | linhas | arquivos |
|---|---:|---:|
| Produto (`src/caissa`) | 81.283 | 143 |
| Testes | 34.745 | 101 |
| Ferramentas | 7.360 | 9 |
| Empacotamento | 4.181 | 9 |
| Documentos | — | 44 |

**Suíte: 3.680 testes, 2 pulados** (WOFF2/Brotli e EPUBCheck, ausências declaradas).
Roda em ~13 min: `.venv\Scripts\python.exe -m pytest tests -q` (3.678 passed, 2026-09-11)
**2026-09-21 (OCR/UI ciclo 2, fase 4, A12):** o EPUBCheck **deixou de ser pulado** nesta máquina —
o jar 4.2.6 vive em `tools/epubcheck-4.2.6/` (ignorado pelo git; `tools/instalar_epubcheck.py`
desempacota o zip da release ou a cópia que o Sigil deixa em `%TEMP%`; `caissa.export.epubcheck`
é o locator/runner que os testes e o `percurso --fluxo livro` partilham). Na primeira corrida
sobre o EPUB do produto ele achou 4 erros (`OPF-028`, prefixo `pdf:`) — corrigidos. Ver
`docs/quality/OCR_UI_REPORT_C2_FASE4.md` §A12.
**2026-09-23 (OCR/UI ciclo 2, fase 5, A15):** a suíte inteira com PyQt6 roda **com** o
`tests/unit/ui/test_arquitetura.py` na mesma corrida (4.004 passaram, 9 pulados) — a afirmação
«importar o arnês não traz um binding de Qt» é feita num processo novo por arnês. Dois
interruptores novos no `OcrServiceConfig`: `table_rows` (B13, a tabela lida por linha) e
`ink_coverage`/`min_ink_coverage` (B14, a leitura que não cobre a tinta não é aceita); toda
corrida de A/B do `bench_sol` passa **os dois** pelo `SOL_CONFIG`. Portão novo do mínimo da
janela: `caissa.ui.audit.minimo` (teto 1250×640) — desde o ciclo 2 do crítico ele mede também o
que fica **à vista** (nenhum controle fora da vista sem barra, nenhum espremido, a mensagem do
rodapé legível com a linha cheia), no mínimo e a 1366×728, com quatro sabotagens (`rodape`,
`corte`, `mensagem`, `aperto`). Grave a saída de cada corrida num arquivo, não num `| grep`: o
filho órfão de uma pele que morreu segura o pipe. Ver `docs/quality/OCR_UI_REPORT_C2_FASE5.md`.
**2026-09-23 (fase 5, ciclo 5 do crítico):** o portão do teclado (`caissa.ui.audit.teclado`) aperta a **tecla** de verdade (`QTest.keyClick`), com o Tab e de volta com o Shift+Tab, e reprova a área onde ela empaca (o foco não sai, ou a tecla escreve no controle) ou põe o foco num controle sem um pixel à vista — a cadeia do foco dizia «50/50» com o Tab preso num editor. Uma rolagem só segue o foco que anda dentro dela: o conteúdo de uma rolagem que o Tab alcança de fora usa `caissa.ui.widgets.foco_a_vista.RolagemSegueOFoco`. O portão da janela assenta a linha do arnês nas duas passadas e tem a sexta sabotagem, `linha`. No árbitro, a concordância entre os motores é medida na ordem em que cada um leu (`arbiter._engine_order`: o B13 move as linhas de uma leitura sem decidir quem ganha); e a página diz o motor que falhou (`OcrEngineBase` marca a leitura vazia `failed`: o RapidOCR roda no processo e, sem memória, falha na alocação).

> **Um teste instável, ainda não diagnosticado (2026-09-10).**
> `tests/unit/model/test_ids.py::test_a_fresh_id_carries_roughly_the_current_time`
> falhou **uma vez** numa execução de `tests/unit`, e **passa isolado** (33/33) e em
> `tests/unit/model` inteiro (1.125/1.125).
>
> O mecanismo está reproduzido e é real: o grampo de monotonicidade
> (`timestamp_ms = max(timestamp_ms, _last_timestamp_ms)`, `ids.py:82`) faz o relógio do
> módulo **nunca voltar**. Empurrando `_last_timestamp_ms` uma hora à frente, toda chamada
> seguinte herda a deriva e o teste (tolerância de 60 s) reprova para sempre.
>
> O que **não** foi estabelecido: quem empurra. Rajada não causa — 300.000 ids em sequência
> dão deriva de 0 ms, porque a aleatoriedade é de 80 bits e o ramo de estouro praticamente
> nunca dispara. Os dois testes que mexem no relógio (`test_edges.py`) salvam e restauram o
> estado sob lock. Bissecção por diretório (`classify`, `detect`, `export`, `index`, `llm`,
> cada um seguido de `test_ids.py`) **não reproduziu**. Não há `pytest-randomly` instalado,
> então a ordem é determinística.
>
> **Reproduzido? Não.** A execução seguinte, mesmo comando e mesma ordem, deu
> **3.243 passed, 1 skipped, 0 failed**. Falhou uma vez em duas. Como a ordem é
> determinística, a causa é de **tempo**, não de sequência.
>
> **O vigia já está instalado** (`tests/conftest.py`, fixture `_vigiar_o_relogio_dos_ulid`).
> Ele mede a deriva depois de **cada** teste e reprova no ato, **nomeando o teste** que
> empurrou o relógio, com tolerância de 5 s. E zera o estado, para que a contaminação não
> se propague pelo resto da suíte.
>
> **Prova de vitalidade feita** (portão sem sabotagem não é portão): um teste que adianta o
> relógio uma hora é acusado pelo nodeid, com a deriva de 3.600.000 ms e o mecanismo
> explicado na mensagem — e o teste seguinte **passa**, provando que o estado foi zerado.
>
> Na próxima ocorrência o culpado virá nomeado em vez de suposto.

**As quinze frentes têm pelo menos um ciclo fechado** — a F2, última a começar, fechou o
seu em 2026-09-11 (`docs/quality/F2_REPORT.md`). Duas passaram por crítica adversarial às
cegas e foram **aprovadas**: tipografia no ciclo 10, interface no ciclo 15, depois de onze
reprovações somadas. A F2 ainda não passou por crítico independente: a leitura lado a lado
foi do construtor.

---

## 2. O que ler, nesta ordem

1. **`docs/ROADMAP.md`** — estado das frentes, placar de reconhecimento, histórico das
   críticas e a tabela dos portões cegos.
2. **`docs/ASSETS.md`** — o que reaproveitar dos cinco projetos e o que **não** reescrever.
   Tem uma seção §2.14 de otimizações **já rejeitadas por medição** — leia antes de propor.
3. **`docs/adr/README.md`** — nove decisões vinculantes, com a justificativa medida.
4. **`docs/quality/CRITIC_CHARTER.md`** — o método de crítica adversarial. A §7 traz duas
   armadilhas de execução que custaram 34 h de processo pendurado.
5. **`docs/quality/CORPUS.md`** — o que conta como medição válida. Número medido fora deste
   corpus não vale para portão nenhum.
6. `docs/SPEC.md` — a especificação. Note que a §13 declara análise com engine fora de
   escopo, e a frente F9 a ligou mesmo assim (ver §6 abaixo).

Os relatórios por frente estão em `docs/quality/F*_REPORT*.md`; as críticas em
`docs/quality/F*_CRITIQUE_*.md`. **Cada número tem o comando que o produziu ao lado.**

---

## 3. Placar de reconhecimento, medido

| métrica | meta | medido |
|---|---|---|
| Recall de detecção (campo) | ≥ 99,0 % | **99,13 %** ✅ |
| Precisão de detecção (campo) | ≥ 98,5 % | **100,00 %** ✅ |
| Segundos por diagrama (vazão, GPU) | ≤ 0,10 | **0,0903** ✅ |
| Diagramas perfeitos em campo, régua corrigida | ≥ 98,0 % | **98,94 %** ✅ |
| Acurácia por casa (divisão de 534) | ≥ 99,95 % | 99,9386 % ⚠️ |
| Diagramas perfeitos, laboratório (divisão de 534) | ≥ 99,0 % | 97,75 % ⚠️ |

**Cuidado com as duas últimas.** Os números publicados antes (99,9854 % e 99,06 %) vinham
da divisão histórica de **320 tabuleiros**. A divisão de teste cresceu para **534** e os
números caíram. **Não é regressão** — é amostra maior. Não compare um com o outro achando
que compara modelo.

**`field_exact` nunca deve ser publicado sozinho.** Ele condiciona na exportação, então um
modelo **menos confiante** pontua melhor nele. Publique sempre com `export_rate` e
`conditional_exact` ao lado. Ver `docs/quality/F4_FIELD_REPORT.md`.

---

## 4. O que fazer a seguir, em ordem de valor

### 4.1 ~~Arbitragem por região no OCR de texto~~ — **FEITO**, ver `F5_REPORT_C2.md`
O laço existe (`src/caissa/ocr/page.py`) e o defeito está fechado — **mas não pelo laço.**

Medi antes de construir: na Gaprindashvili p202 a prosa correta e os lances destruídos
**dividem a mesma linha** (`"For the present White cannot play 1 !txg7 Wxg7"`), então
nenhum corte geométrico os separa. O plano registrado em `F5_REPORT.md` §5 item 1 estava
errado quanto à causa.

Quem fecha é um sinal de token, `mangled_move_ratio` — conta lances que mantiveram a casa
e perderam a peça. **110 páginas de controle têm máximo 0,065; o Gaprindashvili não desce
de 0,195 em 42 páginas.** Limite em 0,15; acima disso a página é aceita a **0,55** em vez
de 0,98, abaixo da barra de 0,82 do árbitro, para o OCR poder concorrer.

**E o defeito era muito maior do que duas páginas: 16 dos 33 livros com camada de texto
têm a notação danificada** — Nunn, Burgess, Yusupov, Euwe Band 7, Polgar, Aagaard. Todos
eram aceitos a 0,98. Dois deles eram os *controles limpos* do próprio corpus.

**Medido em 2026-09-11, e a resposta é interessante.** Nenhum dos dois motores lê os
figurinos: a camada acerta **0,0 % de 1.432 letras de peça** e o Tesseract, 13–22 %. Mas as
falhas têm formas diferentes — o Tesseract erra como **cifra de substituição** (93–98 % dos
erros são de um caractere, `W`=dama, `H`=torre, `S`=rei), a camada erra como **ruído** (204
formas distintas num livro). Cifra se inverte; ruído não. No controle limpo a direção se
inverte por completo (camada 98,8 %, Tesseract 11,3 %), que é por que o limiar existe.

**Mas ainda não conserta página nenhuma**, e isso é o mais importante deste ciclo:
rodando o laço de ponta a ponta apareceram dois defeitos (`F5_REPORT_C2.md` §5).
Cortar a página **lavava o veredito dela** — a p202 voltava de 0,55 para 0,98 e o laço
escalava nada; consertado com a regra «uma região não pode valer mais que a página num
defeito que é da fonte». Esse foi o **15.º portão cego**.

E o **16.º**, que é o mais consequente de todos: a calibração do Tesseract tem um piso
medido em *confiança de palavra* aplicado a um *agregado de página*, e **zera o motor em
12 de 12 páginas**. A cascata não está morta — numa página só de imagem o Tesseract ganha
por ausência de adversário — mas **sempre que o nível 0 produz qualquer texto, ele vence**,
e os níveis 2 e 3 herdariam o mesmo problema. Consertei metade: o termo da «pior palavra»
era a constante 0,000 em toda página de todo livro, e virou um quantil baixo. **O piso não
ajustei de propósito** — escolhê-lo por olho até o Tesseract ganhar é comprar o portão, e
calibrar de verdade exige o corpus da SPEC §11.2.

**O corretor de cifra foi construído no mesmo dia** (`F5_REPORT_C2.md` §6,
`src/caissa/ocr/notation/cipher.py`). Sobre a saída do Tesseract, o ilegível cai de
**78,5 % para 34,3 %** no Gaprindashvili, e 45,7 % dos lances passam a ter casa,
captura e xeque corretos com a peça reduzida a quatro candidatas. Ele resolve a dama
pela **promoção** (`f8=W` ⇒ `W`=dama) e **se recusa a adivinhar o resto** — quem decide é
a reprodução por legalidade, que já existe em `notation/legality_repair.py`.

**Liguei a cadeia inteira no mesmo dia, e o gargalo que eu vinha apontando estava errado.**
Diagrama → FEN → Tesseract → cifra → tronco → legalidade produz **12 lances legais de 18
extraídos em 6 páginas** do Nunn (`F5_REPORT_C2.md` §7) — a primeira vez que o projeto
tira lance legal de um PDF digitalizado ponta a ponta.

O elo que faltava **não era a F2**: era `RegionKind.MOVETEXT`, na taxonomia desde a F1,
com modo de segmentação próprio no Tesseract, e **nunca atribuído por nada**. Sem ele o
repairer recebia 162 tokens de prosa e empatava sete idiomas a 0,01 de confiança. Com ele
(`src/caissa/ocr/notation/movetext.py`) recebe o tronco da análise.

**Duas coisas que a medição forçou e que valem antes de mexer ali:** análise é **árvore**,
e a maior sequência de uma página costuma estar dentro de uma variante — só o tronco começa
no diagrama (a p140 ia de 0 para 4 lances só com isso). Mas o tronco **se emenda por cima**
da variante, porque a linha principal retoma da posição que deixou. Eu tinha dois testes se
contradizendo nesse ponto até a semântica do xadrez decidir.

**O que ainda impede** (§7.5): dano residual de token (`@c2`, `2d2`), `side_to_move` vindo
de `default` em **6 de 9** diagramas, e o tronco nem sempre começar no diagrama. A F2 segue
não iniciada e segue necessária para processar um livro inteiro — mas não era ela que
impedia a cadeia de fechar.

**Cuidado ao mexer no corretor:** ele só pode causar dano numa direção. Quatro falsos
positivos reais apareceram nos controles — notação russa correta, `K` latino num livro
russo, travessão em notação longa, e um livro **português que imprime os lances em
inglês**. Este último, com o alfabeto estreito, reescreveu **oito lances corretos**. Por
isso o padrão aceita as letras de todos os idiomas, e isso custa recall (34,3 % de
ilegível em vez de 4,9 %). **Não alargue o alfabeto para recuperar esse número** — o
caminho é a reprodução por legalidade.

### 4.2 Ampliar o corpus anotado — dá significado a todos os números
A SPEC §11.2 pede **200 páginas** anotadas em dez estratos. Existem **68 páginas / 115
diagramas** (`ChessVisionOFF_Puro/data/field_set.jsonl`).

Consequência declarada em `F5_REPORT.md`: sem ele, as calibrações do árbitro continuam
provisórias, `NONWORD_DETECTION_RATE = 0,55` segue sendo a maior fonte de erro do estimador,
e **não há taxa de erro contra verdade de campo** — só contra a camada de texto dos livros,
que tem erros próprios.

**Três correções de régua pendentes:**
- ~~`CORPUS.md` está errado em dois pontos.~~ **Corrigido em 2026-09-11.** A §0 agora diz
  46 arquivos; a §2 ganhou avisos em E1 e E2 dizendo que o estrato classifica **época e
  qualidade visual, não a camada de texto** — quatro dos cinco E1 falham no nível 0 — e
  nomeando o **Dvoretsky como o único controle nativo do acervo**.
- Um **erro de anotação comprovado** no conjunto de campo (Euwe, *Das Mittelspiel* Bd 7,
  p. 40): o modelo está certo, a anotação errada. Provado pela camada de texto do próprio
  livro (`33. Lf2-d4`, `L` = Läufer = bispo). Correção auditável em
  `benchmarks/field_corrections.json`; **o arquivo do tronco ainda não foi corrigido**, e até
  lá todo relatório de campo carrega 1,06 pp de erro para baixo.
- Os números de laboratório do §3.

### 4.3 Compilar o instalador de verdade
`docs/quality/F12_REPORT_C2.md`. O pacote roda e foi provado executando o `.exe`, mas:
**o instalador nunca foi compilado** (o Inno Setup não está nesta máquina — os 79,4 MB são
medição por compressão equivalente), **não há assinatura de código**, e **nunca rodou numa
máquina Windows limpa sem Python**. O download de pesos nunca tocou a rede (`base_url: null`;
só o caminho offline foi exercitado).

### 4.4 ~~F2 — unificar a ingestão de PDF~~ — **FEITO**, ver `F2_REPORT.md`
`src/caissa/ingest/pdf/` (nove módulos, 5.754 linhas, 166 testes). `import_pdf(caminho)`
devolve um `Document` com proveniência em cada nó; o detector do tronco e o classificador F4
(`combined_finder()`, 911 diagramas lidos em 552 páginas do acervo) são o finder **padrão**
desde o OCR_UI ciclo 2 passo A2 (`PdfImportOptions.detect_raster_diagrams=False` volta à via
vetorial só); `PdfImportOptions.ocr` recebe um
`OcrProvider` para as páginas que o nível 0 rejeita.

**Não era "limpeza interna, sem lacuna visível".** Ligar a cadeia inteira achou cinco
portões cegos em outras frentes (ROADMAP, portões 12–16): a fórmula de coordenadas do
Editor está errada em página girada, o detector vetorial perdia tabuleiros lado a lado
desalinhados, o catálogo tratava `SkakNew-Diagram` como figurino, o nível 0 rejeitava o
Polgar por julgar glifos de tabuleiro como prosa, e todo inteiro na margem virava fólio.

**O que fazer a seguir na F2, em ordem:** (1) crítica independente com
`benchmarks\bench_ingest.py --dump` como material; (2) costurar o `PageRecognizer` da F5
como `OcrProvider` padrão e medir no E8; (3) `Movetext` → `GameScore` pela F6; (4) as 3
páginas do Chernev em que uma tabela de lances vira três colunas (`_columns_are_real`
documenta as duas tentativas descartadas).

### 4.5 Sol — OCR de prosa editorialmente confiável — **ciclo 1 executado**, ver `docs/quality/SOL_REPORT.md`
O item (2) acima está feito e foi além: `PdfImportOptions.enable_ocr=True` liga por padrão o
`OcrService` (`src/caissa/ingest/pdf/ocr_service.py`) — renderização seletiva, laço por
região com decisão `ACCEPTED`/`REVIEW`/`ABSTAINED`, portfólio de pré-processamento
condicionado, calibração ajustada na partição `calib` do corpus dourado, fusão por token,
perfis Tesseract de prosa/lances, replay legal ligado ao diagrama, léxicos empacotados,
traço completo no IR (`ocr_trace.json`) e fila de revisão sem janela. Medido contra o
baseline congelado: CER cai em todo estrato degradado (sombra 0,076→0,031; foto
0,24→0,12; 150 DPI 0,052→0,037), controles negativos 0/9, zero importação silenciosa.

**O que fazer a seguir, em ordem:** (1) rotular scans reais — com FEN de partida dos trechos
de lances — porque 98 % dos lances do corpus hoje não têm posição para o replay e os portões
de CER/lances medem tipografia sintética. **A ferramenta para isso está pronta desde
2026-09-13**: `python tools/rotular.py labeling --pdf <scan.pdf> --reviewer <nome>` (bancada
Tk, linha a linha, com FEN inicial por região), exportação para o manifesto e ajuste fino do
Tesseract (`tools/treinar_tesseract.py`, que exige um modelo float de `tessdata_best` —
`--download-base`); `docs/quality/ROTULAGEM.md` é o guia. **Estado em 2026-09-13 (noite):** 13 páginas
rotuladas (Dvoretsky SFC4 + Modern Endgame Manual), 256 regiões `pdf-scan` no manifesto
privado; o leitor de glifos do tronco é candidato da fusão (figurinas `Hea!`→`♖e8!` sem
treino); o ajuste fino do Tesseract com alfabeto estendido funciona (`caissa_por`: lances nos
scans 52 % → 94 %) **mas regride fora do livro treinado** — modelo é por idioma/livro, treinar
o Dvoretsky a partir do `eng`, não do `por`; o `caissa_eng` entra só como **candidato secundário da fusão** (medido 2026-09-14: lances 75,7 → 82,1 % no corpus, inventados 412 → 317, controles 0 — `ROTULAGEM.md` §4c). **2026-09-14: o ciclo por livro está no pacote**
(`ROTULAGEM.md` §7): `caissa-rotular` abre o PDF, **Treinar…** treina só com as linhas do livro e
registra o modelo para o hash do PDF em `models/tessdata/livros.json`, `PdfImporter` aplica esse
modelo a esse PDF (segunda opinião, nota no relatório) e a nenhum outro, **Medir no livro…** relê
as páginas rotuladas sem e com o modelo por partição. **2026-09-14 (tarde): o livro sai da aba como EPUB/DOCX, inteiro ou por intervalo de páginas** (`ROTULAGEM.md` §7f): `caissa.export.book` compõe F2 → exportador, `caissa-exportar` é a CLI, `caissa.ui.views.exportacao` o diálogo, e o tronco os tem em *Arquivo* (`e98b738`); (2) ~~instalar um segundo motor~~ — **feito em 2026-09-14 (noite)**: RapidOCR 3.x
(Apache-2.0, ONNX CPU) como motor secundário, roteado às páginas degradadas e barrado da
âncora onde há figurinas: lances 0,819 → **0,893**, inventados 291 → **169**, nenhuma
regressão fora do IC (`docs/quality/OCR_UI_REPORT_C1.md` §1 — o plano é
`docs/OCR_UI_ROADMAP.md`, passo 1). Aviso que vale ler: `test_optional_engines.py` injeta
módulos falsos e **não prova** o motor real; o contrato ao vivo é
`tests/integration/test_engine_live.py`. Surya continua por medir (licença dos pesos); (3) a janela de
revisão sobre `caissa.ocr.review.ReviewQueue` quando o shell F9 entrar; (4) `python
benchmarks/sol_gate.py --blind` só num release.

---

## 5. O que NÃO refazer

**Seis otimizações já rejeitadas por medição.** Ver `ASSETS.md` §2.14 e os relatórios:

| ideia | por que foi rejeitada |
|---|---|
| TTA (7 vistas) | ganhou 1 tabuleiro em 320, a 6× o custo |
| Temperatura calibrada (T=1,85) | dobrou a fila de revisão sem consertar uma casa |
| `verify_diagram` por LLM | **especificidade 0,000** — disse "consistente" aos 50 pares certos e aos 50 errados |
| Busca só em meia escala | 2,65× mais rápida e **custa recall** — perde 6 diagramas do `Reinfeld` |
| Estipulação por LLM | invenções de 2 → 12, para **uma** leitura correta a mais |
| OCR de última instância por LLM (`repair_ocr_region`) | conserta 69 lances e quebra 2 — mas escreve **103 lances que não estão na página**; em scan histórico erra mais lances do que acerta (`F11_REPORT_C3.md`) |

**Duas duplicações deliberadas** (`ASSETS.md` §2.15) — não unifique:
- `looks_like_move` é permissivo de propósito; usá-lo como detector de CMap quebrado cega o
  detector, porque uma página inteira de lixo "parece lance".
- O probe de CMap do tronco conta U+FFFD, que dá **zero em 560 folhas** deste acervo — o modo
  de falha real emite codepoints de fonte de xadrez legíveis como latino.

---

## 6. Pendências que exigem decisão humana

1. **A arte das peças é da Chess.com, direitos reservados.** Apurado por comparação de
   imagem (IoU 0,98, canal de cor idêntico) contra o `COPYING.md` de um projeto de terceiro.
   Está **fora do pacote**, substituída pelo conjunto `cburnett`, com licença explícita.
   Decidir: recuperar a original com licença, substituir de vez, ou manter sob consentimento
   para uso próprio. Ver `packaging/licenses/PECAS_PROCEDENCIA.md`.
2. **A licença agregada é AGPL-3.0**, não GPL nem LGPL — o `pymupdf 1.28.2` é
   *"Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License"*. O `pyproject.toml`
   declarava LGPL, o que era falso, e foi corrigido. Sair da AGPL exige trocar o PyMuPDF ou
   licença comercial da Artifex. Ver `LICENSING.md`.
3. **A SPEC §13 declara análise com engine fora de escopo v1**, mas a F9 ciclo 16 ligou o
   Stockfish para três comandos de menu pararem de mentir. Funciona, e **contradiz a spec**.
   Ou a spec muda, ou o escopo volta.
4. **O Gemma 4 12B (7,56 GB) nunca foi medido em nenhum ciclo** — nem no ciclo 3, que
   fechou a medição das cinco tarefas. Recomendação da F11: remover. O E4B (6,15 GB) é o
   embarcado e é 3× mais rápido. Carregado com contexto de 262 k ele fica a 56 % CPU / 44 %
   GPU — não cabe na placa. O `gemma4:e4b` (9,6 GB, sem sufixo) também é redundante: o
   código usa `gemma4:e4b-it-qat` de propósito (`caissa/llm/runtime.py`).
5. **Um link do Gemini** foi citado como origem das ideias deste projeto e **nunca pôde ser
   lido** — `gemini.google.com` é bloqueado por política de rede nesta máquina. Todo o
   trabalho partiu da descrição em prosa do usuário.

---

## 7. A lição que vale mais que o código

Vinte e um instrumentos de medição foram encontrados **cegos** durante o projeto. Em todos,
**a suíte de testes estava verde e a funcionalidade estava quebrada**:

| # | o portão media | o que estava quebrado |
|---|---|---|
| 1 | dispersão do pé de coluna | comprada distribuindo buracos no corpo da página |
| 2 | `bool(nome)` | 34 controles anunciavam "121" a leitores de tela |
| 3 | strings de token | cego à identidade da peça — dama por cavalo passava |
| 4 | amostra única de perfil | sempre a chamada C mais longa, nunca 108.620 miúdas |
| 5 | token de cor opaco | sem compor o alfa que o Qt de fato aplica |
| 6 | linhas justificadas | **excluía as linhas que se recusou a justificar** |
| 7 | `toolTip()` como "na tela" | nada desenhado |
| 8 | certidão de higiene | conferia o arquivo Tk enquanto o Qt era reescrito |
| 9 | uma pele de três | o defeito vivia na pele não medida |
| 10 | seis abas de doze diálogos | a varredura rodava uma vez, antes de os diálogos nascerem |
| 11 | a fonte do widget | a tela pinta a fonte da folha de estilo |
| 12 | duas tabelas coincidentes | acertava por coincidência, não por construção |
| 13 | todo sinal léxico do nível 0 | a prosa domina a contagem: **16 livros com a notação destruída passavam a 0,98** |
| 14 | as caixas do nível 0 no laço novo | o teste não passava raster, então a translação era no-op; com raster, caixas ao **dobro do deslocamento**, fora da página |
| 15 | o veredito por região | cortar a página **lavava** a acusação: 0,55 na página, 0,98 nas duas metades |
| 16 | a calibração do Tesseract | piso medido em *palavras* aplicado a um *agregado de página* — motor zerado em **12 de 12**, cascata decorativa |
| 17 | os dois espaços de coordenadas do PDF (F3-A) | a fórmula do Editor **soma a origem da CropBox**: em página girada com CropBox deslocada o tabuleiro cai 40 pt longe da tinta |
| 18 | o detector vetorial (F3-A) | dois tabuleiros lado a lado em alturas diferentes: **0 de 2** no Dvoretsky p. 203, e 16 rótulos de coordenada viravam parágrafos |
| 19 | o catálogo de fontes (F3-A) | `SkakNew-Diagram` caía no padrão de figurino — 5.334 diagramas do Polgar invisíveis à via exata |
| 20 | o veredito da camada de texto (F5) | julgava glifos de tabuleiro como prosa: Polgar rejeitado em **11 de 11** páginas por "8 % de palavras" |
| 21 | a mobília de página (F5) | todo inteiro na faixa de margem era fólio — o `22` de uma linha tabular do Chernev sumia |

Nenhum foi encontrado por mais teste. Doze por **crítica adversarial independente**, com
mandato de reprovar, obrigação de remedir do zero, e liberdade para sabotar o próprio
portão. O 13.º por **medir a premissa de um plano antes de executá-lo**. O 14.º por
**releitura do código depois de a suíte ficar verde**. O 15.º e o 16.º por **rodar o
sistema inteiro de ponta a ponta com os motores reais** — os testes de costura usavam um
motor falso, e um motor falso nunca revela que o verdadeiro não consegue ganhar. E os
cinco últimos (17–21) num só dia, por **ligar a ingestão de PDF de ponta a ponta sobre o
acervo inteiro** e ler cinco páginas lado a lado com o impresso (`F2_REPORT.md` §3, §5):
cada um só se manifesta quando uma página real, com sua tipografia, atravessa a cadeia.

Os quatro últimos têm a mesma moral por ângulos diferentes: **um portão verde não é
evidência de nada até alguém tentar quebrá-lo**, e um sistema testado só por partes não
foi testado.

**A prática que ficou, e que deve continuar:**

> **Todo portão novo precisa de uma sabotagem que o faça reprovar.**
> Um portão que só devolve zero é indistinguível de um portão cego.

Em um dos casos a própria prova de vitalidade estava cega — **duas vezes** — e isso só
apareceu porque o construtor a rodou sabotada **antes de confiar nela**.

---

## 8. Ambiente

```
Python 3.11.9 · .venv na raiz · torch 2.11.0+cu128
GPU: RTX 5060, 8 GB, sm_120 (Blackwell) — exige rodas cu128 (ADR-0003)
Ollama 0.34.0 · gemma4:e4b-it-qat embarcado
Disco C: 38,4 GB livres (eram 76,4 no início do projeto)
```

Saúde do ambiente: `.venv\Scripts\python.exe scripts\doctor.py`
Ele **prova a GPU com kernel real**, não com `torch.cuda.is_available()` — que devolve
`True` mesmo sem kernels para a arquitetura, e é o modo de falha silenciosa do Blackwell.

`.venv-pack` e `dist/` podem ser apagados quando não estiver empacotando.
