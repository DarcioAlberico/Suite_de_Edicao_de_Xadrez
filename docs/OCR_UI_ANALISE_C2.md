# Análise — ciclo 2: onde o OCR de diagramas, o OCR de texto, os glifos de xadrez e a interface ainda perdem

> **Data:** 2026-09-20 · **Papel:** análise de lacunas, sem código alterado. Sucede
> `docs/OCR_UI_ANALISE.md` (2026-09-14), cujas 15 alavancas foram executadas até onde a
> dependência humana permite (`docs/OCR_UI_ROADMAP.md` §4; `docs/quality/OCR_UI_REPORT_C1.md`
> §0–§19.5). Este documento **não repete as 15 alavancas**; onde retoma um experimento
> anterior (o aumento `mhsp` da S-40, §3.4) diz por quê, com que hipótese nova e com que ablação.
> **Fontes:** o código da suíte (`src/caissa/**`) e do tronco (`..\ChessVisionOFF_Puro\src\
> chess_diagram_ocr\**` — abaixo, prefixo `tronco:`), lidos função a função por cinco analistas
> (§1), e os relatórios `OCR_UI_REPORT_C1.md`, `SOL_REPORT.md`, `sol/sol.json`,
> `sol/c1_anchor.json`, `sol/c1_rapidocr.md`, `F4_FIELD_REPORT.md`, `F4GPU_REPORT.md`,
> `ROTULAGEM.md`, `HANDOFF.md`, `0b/propostas_0b.md`, `tronco:docs/EXPERIMENTS_FASE7.md`,
> `tronco:docs/ROADMAP_FASE7.md`, `benchmarks/reports/vector_survey_20260914_175821.json`.
> **Regra dos números:** todo número de relatório traz a origem ao lado. Os marcados
> **(medido nesta análise)** vieram de execuções curtas — `python -c`, contagens, uma corrida de
> `tools/f4_field_failures.py --barrados` (~1 min, ferramenta determinística; o §19.5 do C1 a
> rodou 3× com saída idêntica) — feitas para *confirmar um comportamento do código*, não para
> medir um portão: o construtor os remede com o instrumento nomeado antes de publicar. Os
> marcados **(extrapolado)** são aritmética sobre um número de relatório. Nenhum portão foi
> rodado aqui. Caminhos sem prefixo são da suíte, relativos a `src/caissa/` quando o módulo é
> óbvio pelo nome (`importer.py` = `src/caissa/ingest/pdf/importer.py`).
> **Revisão adversarial:** aprovada pelos dois críticos (Claude no ciclo 3, Codex no ciclo 4);
> §11 registra o que mudou e `docs/quality/OCR_UI_ANALISE_C2_CRITICAS.md` guarda os vereditos.
> **Documentos derivados** (a escrever depois da aprovação): `OCR_UI_SPEC_C2.md` e
> `OCR_UI_ROADMAP_C2.md`, no molde dos do ciclo 1.

---

## 0. Em uma tela

O ciclo 1 mediu e fechou quase tudo que os relatórios *nomeavam*. O que ficou é de outra
natureza, e os cinco levantamentos independentes convergiram nela: **o produto não faz o que
o benchmark faz**. Os instrumentos ligam o detector raster, o pacote de recall, o modelo do
livro; a janela e a exportação não. E onde o produto faz, **o sinal morre na fronteira**
entre módulos (tronco → suíte → IR → exportação) ou **se perde em silêncio** por um detalhe de
string. Nenhuma das alavancas abaixo pede um modelo novo; quase todas pedem fiação, uma
gramática comum ou um portão que hoje passa cego.

As 20 alavancas com maior valor esperado sobre custo, por ordem; o resto está nas seções.

| # | alavanca | área | evidência (resumo; detalhe na seção) | ganho esperado (hipótese) | custo | risco |
|---|---|---|---|---|---|---|
| 1 | **A importação e a exportação do livro nunca leem diagrama raster** — `importer.py:688-690` cai em `vector_diagram_finder`; `ui/views/importacao.py:114-122`, `ui/views/exportacao.py:384-392`, `export/book.py:340` não passam `diagram_finder`; `combined_finder()` só roda em `benchmarks/` | diag+UI | survey 2026-09-14: 2 livros `fonte`, 5 `misto`, 15 `imagem-embutida`, 18 `scan` — só os 2 (e parte dos 5) têm diagrama vetorial; Aagaard p31 (`imagem-embutida`) importado com opções padrão: **0 diagramas; com `combined_finder()`: 2** (medido nesta análise); C1 §17.4 registrou "nada é duvidoso" no Kemeri, que tem diagrama na p. 80 | o EPUB/DOCX de qualquer livro não vetorial passa a ter diagramas; o trilho passa a ter duvidosos | baixo (**depois** da alavanca 6 — §3.3) | tempo de importação (0,38 s/diag fluxo único, `F4GPU_REPORT.md` l.25-31); VRAM partilhada com o OCR; **o `recall_pack` é monkeypatch global sem lock** — ligar o finder numa thread da janela antes de internalizá-lo faz a detecção da página visível correr ora com ora sem o pacote (§3.3) |
| 2 | **A correção feita na janela não chega ao EPUB/DOCX** — `_export_book` reimporta o PDF do zero; só `ReviewDecisions` (texto) é aplicada; `Ponte.resultado` (minutos de OCR) não é lido por ninguém | UI | `export/book.py:339-354`; `tronco:qt/importador_de_livro.py:83-116`; `ui/audit/percurso.py:263-269` conta "gravar a correção" com `lambda: True` e 279-292 só confere `destino.exists()` | o fluxo U6 "corrigir → exportar" fecha; o portão deixa de passar cego | médio | IoU errado casa decisão com o diagrama errado — teste unitário |
| 3 | **Página digitalizada não tem leiaute** — PDF de imagem → `_whole_page` → uma região `PAGE`, PSM 3; `layout/analyze.py lines_from_result` existe e ninguém chama | texto | `ocr/page.py:336-354`; `c1_anchor.json` recontado (medido nesta análise): `scan_clean_300` coluna única **0,0052** (101 itens, na meta), **duas colunas 0,1254** (26 itens); `twocol:d:9`: linhas de ~2.300 px atravessando a calha (~90 px, medida na imagem), escore 0,927, decisão **aceito**, CER 0,688 | CER limpo e 150 DPI fecham por leiaute, não por motor; `MOVETEXT` em scan passa a existir (destrava Nunn 0/99) | médio | coluna única partida — `LINHAS_NA_CALHA=1` do tronco, controle Darcy Lima 0/39 (`tronco:text/colunas.py`) |
| 4 | **`Nf6⩲`, `Nf6±` e LAN com travessão tiram lances da partida em silêncio** — `_TRAILING_JUNK`/`_MOVE_SHAPE` têm `⧱⧲` (U+29F1/2) no lugar de `⩱⩲` (U+2A71/2); `_MOVE_SHAPE` não aceita os travessões que o mesmo arquivo define em `_DASHES`; `±∞=` não fazem parte de "lance" em cinco gramáticas e em dois instrumentos | glifos | `notation/legality_repair.py:143,148,338`; `repair_movetext('1.e2—e4 e7—e5 2.Ng1—f3 …') → 0 lances, unresolved=()`; via de produto `game_from_paragraph` com `Nf6±` ou `Nf6⩲`: 7 lances em vez de 10 (medido nesta análise, comandos em §5.2) | lances de fim de variante (Informator/Quality/Thinkers) e partidas em LAN (russo, Informator antigo) deixam de sumir | baixo | `=` de prosa virar lance — a forma exige fileira |
| 5 | **Lances atribuídos ao diagrama errado em silêncio; roque com número colado corta a partida sem rasto** — `games.py:273` devolve `anchors[-1].fen` quando nenhum diagrama casa; `5.O-O` não é lance para `movetext._is_move` nem para `_GLUED_NUMBER` | glifos+texto | `ingest/pdf/games.py:60,273`; `ocr/notation/movetext.py:55,100-104`; `game_from_paragraph` sobre `1.e4 … 4.Ba4 Nf6 5.O-O Be7 …` → 8 lances, `comment_after='[não reproduzidos: Be7]'`; com `5. O-O` → 16 (medido, §5.3) | `games_gate` deixa de contar partidas plausíveis-e-erradas; `RepairReport.skipped` nomeia o que foi pulado | baixo | cobertura cai onde o fallback acertava por sorte — o portão diz quanto |
| 6 | **O `recall_pack` (recall 0,9478 → 0,9913) não corre em lugar nenhum do produto** — é um `contextmanager` que monkeypatcha `_extract_candidate_quads` e `candidates_from_embedded_images`, ativo só no finder da suíte e nos benchmarks; a janela chama `detect_diagrams_in_pdf_page` direto | diag | `vision/detect/recall.py:232-338`; `tronco:qt/janela.py:1154,1161,1227`; grep `recall_pack` no tronco: 0; `ROADMAP.md` l.157-166 | 1 diagrama em 20 que a janela não mostra passa a aparecer; a alavanca 1 fica segura | baixo–médio | +tempo de detecção (multiescala soma passes) — `profile_detection.py` |
| 7 | **A fusão julga o texto fundido com o escore da âncora** — uma leitura certa do leitor de glifos (aceita a 1,00) é jogada fora porque o Tesseract abstém a 0,40 | texto | `ocr/fusion.py:318-338`; `ingest/pdf/ocr_service.py:980-995` (`_settle`); `real:Dvoretsky…:11:164:53`: fundido `53 ♔g1 ♖h8 / EA ♖b2 ♖e8` → ABSTAINED; 33 dos 62 abstidos do `native` têm secundário aceito/revisão (medido nesta análise) | linhas de solução sob diagramas passam a ir à revisão em vez de sumir | baixo | glifo no ruído virar revisão inútil — `sol_gate` controles 0/9 |
| 8 | **Sósias viram "lances apoiados" que a fusão nunca troca** — `is_move_token` aceita `8c4`, `2c7`, `Ae5` (união de 8 idiomas + fileira sem peça); `_LINK_MARKS` sem travessão destrói `b2—b4`; `_figurine_cut` exige o mesmo prefixo (`17...Ae5` × `7...♘e5`) | texto+glifos | `ocr/lexicon.py:376-405,384,598-610`; `ocr/fusion.py:353-372,405-431,514-522` | parte dos 169 inventados (`c1_rapidocr`) e dos 11 lances que o modelo do livro lê sozinho e a fusão perde (204/204 × 193/204, `ROTULAGEM.md` §4d, C1 §8) | baixo | idioma detectado errado marca lances como duvidosos — `sol_gate` por estrato `authored:es/de` |
| 9 | **No PDF exportado as figurinas e ⩲⩱⨁ desaparecem sem aviso** — `_face` escolhe só roman/bold/italic de `times.ttf`/`georgia.ttf`, que não têm U+2654–265F; `has_char` filtra o caractere; a fidelidade relê a sidecar JSON, não o PDF | glifos | `export/pdf.py:113-118,733-750,1226,1374`; `export/fidelity.py:396-408`; fontTools nesta máquina: times/georgia/arial/DejaVuSerif **0/12** figurinas, `seguisym.ttf` 12/12 (medido nesta análise); `NAG_SYMBOLS` diverge da `nag_table`; LaTeX russo com `N→Ко` | o PDF exportado deixa de ser o único formato com figurinas mudas | baixo–médio | métricas ao misturar faces numa linha — `test_pdfwrite` |
| 10 | **Ler a página não tem progresso, não cancela, tranca o editor inteiro, e o primeiro clique paga o modelo às cegas**; a importação só cancela **entre páginas** | UI | `tronco:qt/janela.py:1304-1331,1903-1910`; `tronco:service.py:536-546,577-585`; `tronco:ui/busy.py:251-256` lista `_rodar` em `FORA_DO_REGISTRO`; `importer.py:605-607 _check_cancel` por página, `ocr/engines/tesseract.py:197 timeout_s=180`; tempo até o primeiro resultado a frio: **não medido** | SPEC §10.5 vale para o gesto mais frequente | baixo–médio | `test_busy.SEM_REGISTRO` muda junto |
| 11 | **O sinal por casa morre na fronteira tronco → suíte** — `DiagramHit` não tem campo por casa; `_diagram_node` deixa vazios `per_square_confidence`, `repairs`, `alternatives`, `model_hash`; a janela calcula `changed_squares` e `orientation_ambiguous` e não os mostra (o conflito de lado **já é mostrado**) | diag+UI | `importer.py:164-191,1301-1318`; `tronco:service.py:97-171`; `tronco:qt/painel_de_resultado.py:1184-1203` (1195 → `strings.side_source_label(conflicting=)`) | o âmbar chega ao livro (HTML/EPUB/revisão); "reparado"/"orientação ambígua" viram estado com ação | baixo | ordem a1..h8 × a8..h1 — teste de paridade com `uncertain_squares` |
| 12 | **O cache de 8 páginas descarta correções à mão com um `logger.warning`; fechar a janela com edições não pergunta; trocar o lado não desfaz** | UI | `tronco:ui/page_results.py:39,139-157`; `tronco:qt/janela.py:1923-1927`; `tronco:qt/painel_de_resultado.py:888-897` | SPEC §10.7 (desfazer universal) e "perda de trabalho ao fechar" da Carta | baixo | perguntar demais — só com `has_hand_edits` |
| 13 | **O aumento dirigido S-40 (`mhsp`) nunca entrou na produção, e nenhum aumento toca espessura de traço** — o `.pt` de produção é `aug0`; `mhsp` reduziu reparos 15 → 9 e foi reprovado "pela letra" sobre 38 diagramas; a janela treina sempre `AugmentConfig()`; **10 das 27 casas erradas do campo hoje são de cor** (11 pelo `argmax`), 4 delas `q→Q` no Koblenz a 0,71–1,00 | diag | metadados de `models/piece_classifier.pt`; `tronco:docs/EXPERIMENTS_FASE7.md:989-1016`; `tronco:augment.py:53-63`; `tronco:ui/pedido_de_treino.py:72-79`; `f4_field_failures.py --barrados` sobre `d39b1f1` (medido nesta análise, §3.4) | os 7 barrados por reparo e as 10 casas de cor — com ablação `aug0` × `mhsp` × `mhsp+RandomStroke` | médio | catraca de laboratório — `lab_gate.py --runs 3` |
| 14 | **O leitor de glifos foi absorvido sem a pós-cadeia do tronco** — `empilhados.unir`, `colados.separar`, `unir_pingos(binaria=)` não são chamados: `=`, `:`, `;` têm recall 0 (o tronco mediu); `margem()` existe e nada a usa; sem classe de rejeição | glifos | `ocr/engines/glyph.py:171-179,247-256`; `tronco:text/leitor.py:427-433,551-596`; `tronco:text/empilhados.py:12-16`; `tronco:text/modelo.py:373-390`; 314 classes (`ROTULAGEM.md` §4); "2,3 pontos de F1" sem árbitro: `tronco:text/colados.py:14` | `g1=♕` e avaliações `=` passam a ser lidas; a margem vira 2.º critério da troca sósia→figurina | baixo | `colados` só com árbitro |
| 15 | **Importar/exportar trancam todas as abas; três aberturas de PDF na mesma janela; o OCR do livro roda duas vezes** | UI | `tronco:qt/janela.py:990-998,463-468,527,939-941`; `ui/views/revisao_de_texto.py:101-170,241-258`; 8 páginas com OCR = 31,9 s (C1 §17.3) → 289 páginas ≈ 19 min **(extrapolado, linear: 289 × 31,9 s / 8 = 1.152 s)** sem editar nada | editar enquanto importa; revisar texto sem reabrir o PDF | baixo | duas escritas em `labeling/revisao/<livro>.json` — lock |
| 16 | **Nenhum NAG sobrevive à via PDF → GameScore**; `²³µ¹` e Informator só são mapeados ao colar; `⇄`/`△`/`⊕` sem alias | glifos | `ingest/pdf/games.py:158-178`; `notation/book_import.py:670`; `ingest/pdf/textlayer.py:104-125`; 6 de 20 símbolos Informator sem `canonical_code` (medido nesta análise) | o PGN sai com a avaliação do autor | baixo–médio | `N` de novidade × cavalo — `suffix_nag_pattern` |
| 17 | **O perfil de lances do Tesseract (SOL-7) só roda quando ≥ 50 % dos tokens da página inteira são lances** — `MOVETEXT` por `kind` só com `kind is MOVETEXT` (em scan `kind` é sempre `PAGE`), ou por `_looks_like_movetext(result)` sobre a página inteira; e só se o vencedor for o Tesseract. Numa página mista de livro (prosa + análise, sempre < 50 %) nunca | texto | `ocr/engines/profiles.py:59-60`; `ingest/pdf/ocr_service.py:759-777,1163-1169` | o ganho medido do SOL-7 (CER 0,0168 → 0,0066 em movetext puro, `SOL_REPORT.md` §4) chega às páginas mistas | baixo–médio | +1 Tesseract por faixa — `s/MP` |
| 18 | **A segunda opinião local está morta desde o corte do Tk; a preferência continua no diálogo** — no Niemeijer (confiança mínima **média** 0,25, zero acima do gate) o conjunto em desacordo cobriu **exatamente** os erros nos 3 diagramas conferidos à mão: 4/4, 23/23, 41/41 | diag+UI | `tronco:docs/ROADMAP_FASE7.md:1493-1503` (S-66); `tronco:653f88b` apagou `ui/second_opinion_button.py`; `mark_second_opinion` só em testes; `tronco:ui/configuracoes.py:116-127` | onde o modelo desaba, o revisor confere as casas em disputa, não 64 | baixo–médio | o segundo leitor tem de ser de **outra família** que o de produção (§3.5); 7 s / 232 MiB no 1.º carregamento — `bloqueio` |
| 19 | **O trilho não aprende com o que a pessoa corrige; "primeira duvidosa" é o único navegador; a hesitação (âmbar) não conta como dúvida; o tabuleiro não recebe teclado** | UI | `tronco:qt/trilho.py:254-286`; `ui/trilho.py:112-138`; `tronco:qt/tabuleiro_editavel.py` sem `keyPressEvent`/`setFocusPolicy`; `tronco:ui/atalhos.py` 25 `Atalho(` (medido) e 0 comandos das abas da suíte em `ui/comandos.py` | corrigir pelo teclado em ≤ 3 teclas por casa; navegar dúvidas | baixo–médio | letras roubadas de campos de texto — guarda de foco existente |
| 20 | **A fusão compara confianças cruas de motores incomparáveis** embora a calibração por palavra exista (68 tabelas, C1 §1); o RapidOCR replica o escore da linha em cada palavra | texto | `ocr/arbiter.py:385-412`; `ocr/fusion.py:119,482,487-488,527`; `ocr/engines/rapidocr.py:442-477`; `c1_rapidocr.md` calibração ECE 0,139 | trocas decididas por décimos passam a ter escala comum | baixo (+ recalibração) | os três limiares mudam de sentido — remedir na `calib` |

O que **não** está nesta tabela e por quê: §9 (medido e rejeitado no ciclo 1 e antes, mais o
que os cinco levantamentos foram verificar e o código já resolve).

---

## 1. Método

Cinco levantamentos independentes, em paralelo, sobre o mesmo briefing (o que já está feito,
o que foi rejeitado, o formato exigido: evidência caminho:linha ou relatório§, por que o
usuário sente, alavanca, instrumento existente ou sabotagem do novo, custo, risco, novidade):
quatro exploradores Claude por área (diagramas, texto, glifos, interface) e o **Codex**
(`codex exec`, só leitura) como quinto analista **transversal**, encarregado do que cai entre
as áreas. Cada um entregou também "o que parecia lacuna e não é" (§9.2). A síntese conferiu
no código as afirmações que sustentam a tabela do §0. O documento passou por dois críticos
adversariais independentes (Claude e Codex), regidos pela `CRITIC_CHARTER.md`, que
reproduziram os "(medido nesta análise)" e reprovaram a primeira versão — o que mudou está
no §11.

Duas regras do ciclo 1 continuam valendo para tudo que se propõe aqui: portão novo só com
sabotagem que o faça reprovar; nenhum número em relatório sem comando e estratos.

---

## 2. O fio que atravessa as quatro áreas

### 2.1 O produto não é o benchmark

| o instrumento liga | o produto | onde |
|---|---|---|
| `combined_finder()` (vetor → fonte inferida → raster com classificador) | `vector_diagram_finder` — diagrama vetorial só nos 2 livros `fonte` e em parte dos 5 `misto` | `importer.py:688-690`; `ui/views/importacao.py:114-122`; `ui/views/exportacao.py:384-392`; `export/book.py:340` |
| `recall_pack()` (recall 0,9478 → 0,9913, `ROADMAP.md` l.157-166) | detecção crua do tronco | `vision/detect/recall.py:232-338`; `tronco:qt/janela.py:1154,1161,1227` |
| `--augment mhsp` (S-40: reparos 15 → 9) | `AugmentConfig()` = `aug0` | `tronco:ui/pedido_de_treino.py:72-79`; metadados do `.pt` |
| segunda opinião (`tronco:second_opinion.py`; S-66) | botão apagado no corte do Tk | `tronco:653f88b` |
| `acquire_square_classifier` (residência, ADR-0004) | `load_classifier()` por finder, warm-up a cada importação | `vision/classify/residency.py` sem chamador; `ingest/pdf/finders.py` |
| `PortfolioConfig.verso` (redutor de transparência com o verso real) | nunca preenchido | `ocr/portfolio.py:346`; `ocr/preprocess.py:621-665` |
| `learn_from_board` (assinatura → peça por livro, via vetorial) | sem chamador | `vision/detect/vector_detect.py:81,765-798` |

Consequência prática: os números publicados de detecção e recall (`ROADMAP.md` §F3/F4)
descrevem o benchmark; o que o usuário obtém ao importar um livro não vetorial é **zero
diagramas** (alavanca 1). É a lacuna de maior valor deste ciclo — e só é barata depois de o
`recall_pack` deixar de ser monkeypatch (§3.3).

### 2.2 O sinal morre na fronteira

- tronco → suíte: confiança por casa, reparos, alternativas, `model_hash` (alavanca 11);
- serviço → janela: `changed_squares`, `orientation_ambiguous`/`orientation_reason` calculados
  (`tronco:service.py:97-171`) e não mostrados — `side_conflicting` **é** mostrado
  (`painel_de_resultado.py:1195` → "texto e posição discordam — confira", `ui/strings.py:42`)
  mas sem ação ligada;
- fusão → IR: `chosen_from`/confiança por token vivem só no `trace()`; `PieceGlyph` não tem
  proveniência e `figurine_set` nunca é definido (♕ contorno vira ♛ sólido — §5.7);
- IR → PGN: `MoveNode.nags` nunca preenchido na via de importação (alavanca 16); o PGN do
  tronco grava 8 cabeçalhos e perde `image_hash`, reparos por casa, decisão humana (§7.4);
- janela → exportação: `Ponte.resultado` e as correções de casa (alavanca 2);
- revisão → aprendizado: `corrections()` devolve uma lista; recalibrar e retreinar são manuais
  (§7.6).

### 2.3 Perdas silenciosas

Onde o código descarta sem dizer: `⩲⩱`/`±` (alfabeto de cauda) e travessão em LAN e `5.O-O`
(número colado) tiram lances da partida com "skipped, not failed" — a partida inteira, no caso
do travessão; `anchors[-1].fen` atribui lances ao diagrama errado; `_try_ocr` que devolve
**vazio** deixa a camada acusada voltar como `"text-layer"` (a exceção, ao contrário, é anotada
em `report.notes` — §7.2); o PDF exportado apaga caracteres sem fonte sem `context.note`; o
LRU descarta correções com um `warning` no log; o alt text descreve tabuleiro vazio como
"jogam as brancas" (§7.7); o cancelamento da importação só olha entre páginas, e dentro de uma
página até ~8 chamadas de Tesseract com `timeout_s=180` não são canceláveis (alavanca 10).
Cada uma viola a Carta §3.3 ("falha silenciosa", "operação longa sem cancelamento") e nenhuma
custa mais de um dia.

---

## 3. OCR de diagramas (visão)

### 3.1 Onde está

| métrica | meta | medido | fonte |
|---|---|---|---|
| diagramas perfeitos em campo, régua da anotação | ≥ 98,0 % | 103/114 casados exatos; 11 errados em 27 casas, **10 de cor**; exportados 100/103, `field_exact` 0,9709 | `f4_field_failures.py --barrados` sobre `tronco:d39b1f1` (medido nesta análise; §19.5 do C1 deu 104/114 com a régua corrigida) |
| AUROC da confiança por diagrama | ≥ 0,90 | 0,899 (`min_confidence` sozinho 0,966) | `OCR_UI_REPORT_C1.md` §19.5 |
| laboratório, diagramas perfeitos (split 534) | ≥ 99,0 % | 97,75 % | `F4_FIELD_REPORT.md` §8.3 |
| recall de detecção (campo) | ≥ 99,0 % | 0,9913 **com `recall_pack`**; tronco sem mudança 0,9478 | `ROADMAP.md` l.157-166 |
| s/diagrama (GPU, 6 processos) | ≤ 0,10 | 0,0903; fluxo único 0,38 (detecção 0,14, contexto de texto 0,11, decodificação 0,08, render 0,04, GPU 0,01) | `F4GPU_REPORT.md` l.25-31, l.348 |

As 27 casas erradas de hoje, por livro (medido nesta análise; a correção do Euwe p40 em
`field_corrections.json` **não** se aplica a esta ferramenta — `HANDOFF.md` §4.2):

| livro | diagramas errados | casas erradas | de cor (X↔x) na leitura final | reparadas pelo decodificador **e erradas** |
|---|---|---|---|---|
| Koblenz p30/p50 | 4 | 1+4+1+1 = 7 | **5**: 4 do classificador (`q→Q` ×4, a 0,71–1,00) + 1 do decodificador (`g1 K→k` sobre um `K` certo a 0,48) | 2 (`g6 k→vazio` — o `argmax` dizia `K`; `g1 K→k`) |
| Niemeijer p20 | 3 | 8+1+1 = 10 | 3 | 0 |
| Levenfis p150 | 1 | 3 | 0 | 1 |
| Stefaniu p100 | 1 | 3 | 1 (`f1 B→b`) | 1 (`e1 K→vazio` — o `argmax` dizia `k`) |
| Euwe p40 | 1 | 3 | 0 | 0 |
| Burgess p60 | 1 | 1 | 1 (`e5 q→Q` a 1,00) | 0 |

"De cor" compara a **leitura final** (depois do decodificador) com a verdade: 10 casas. Pelo
`argmax` do classificador — o que D3 e D6 querem mover — são 11 (as 10 menos `g1 K→k`, que o
decodificador fez, mais `g6` e `e1`, que o decodificador esvaziou depois de o classificador
errar a cor de um rei). Reparos do decodificador no campo: **14 casas em 7 diagramas, 10
certas, 4 erradas** (`totals.repaired_squares`); 3 das 4 erradas partem de um rei cuja cor o
classificador trocou ("dois reis brancos") — o decodificador resolve a violação esvaziando ou
recolorindo o rei errado.

O Koblenz caiu de 8–11 casas por diagrama (C1 §19.2) para 1–4 depois do `tighten_board`
(`tronco:d39b1f1`): o que era recorte foi resolvido; **o que sobrou é cor** — 4 `q→Q` com
confiança 0,71–1,00 (o sintoma exato do F4 §4.2: `q→Q` 48 vezes em 86 conjuntos) e uma casa
que o decodificador estragou a partir de um rei recolorido.

### 3.2 D1 — Ler diagrama raster no produto (alavanca 1)

`importer.py:688-690`: `finder = options.diagram_finder or (vector_diagram_finder if
detect_diagrams else None)`. Nenhum chamador do produto passa `diagram_finder`;
`HANDOFF.md` l.213 diz que se liga com `combined_finder()` e ninguém o faz. Medido nesta
análise: Aagaard índice 31 (`imagem-embutida` no survey) → 0 diagramas; com
`combined_finder()` → 2 localizados, 2 lidos (índice 30 dá 3). O trilho (`ui/trilho.py`)
conta `relatorio.diagrams` — por isso "nada para rever".

**Alavanca.** `ui/views/importacao.py`, `ui/views/exportacao.py`, `export_book` passam
`diagram_finder=combined_finder(classifier=…)`; o classificador é carregado uma vez por
sessão com `acquire_square_classifier` e partilhado com a janela. **Pré-requisito:** D2 —
hoje `combined_finder` (`finders.py:111`) roda dentro de `recall_pack()`, que troca **sem
lock** `board_detection._extract_candidate_quads` e `hybrid.candidates_from_embedded_images`
(`recall.py:232-296,309-318`); a importação da suíte corre numa `threading.Thread`
(`importacao.py:87-93`) no mesmo processo em que `DeteccaoDeFundo` (`tronco:qt/janela.py:293,
1159-1161`) detecta a página visível: duas entradas concorrentes empilham `patched` sobre
`patched`, e a janela detectaria ora com ora sem o pacote. **Medir.** `benchmarks/bench_ingest.py
--raster`; `caissa.ui.audit.percurso --fluxo livro` ganha a asserção "diagramas ≥ 1 num livro
não vetorial" — sabotagem: sem finder → 0 → REPROVA. `side_to_move_gate`/`games_gate` já rodam
com o `combined_finder`.

### 3.3 D2 — `recall_pack` dentro do detector (alavanca 6)

As três recuperações (`rescue_squares`, multiescala somando, piso de contraste no embutido —
`recall.py:26-44`) entram em `tronco:board_detection.detect_boards` como opção, deixando de
ser monkeypatch; a janela e a suíte passam a chamar a mesma função. **Medir.**
`validate_detection.py` (as variantes da tabela do `ROADMAP.md` l.157-166) e `field_exact.py
--variant baseline` passam a coincidir com `recall-pack` (0,9913 / 1,0000). Sabotagem: ficar
só com o piso de contraste → recall volta a **0,9478** (linha "só piso de contraste no
embutido"); ou só multiescala → 0,9826.

### 3.4 D3 — O aumento que nunca entrou, e o eixo que nenhum aumento cobre (alavanca 13)

Produção `aug0` (blur p 0,3, jitter de brilho/contraste 0,3, affine 2°; `tronco:training.py:
175-183`); as cinco dirigidas (`hflip, hatch, speckle, paper, invert`) a 0,0 (`augment.py:
59-63`). Nenhuma mexe em **espessura de traço** nem em **contorno × preenchido** — o modo de
falha nomeado no `0b/propostas_0b.md` l.14 (Koblenz: pretas traço grosso, brancas contorno), do
Burgess e5 (F4 §4) e das 10 casas de cor de hoje (§3.1). Duas observações de código:
`RandomInvert` (`augment.py:201-205`) inverte **sem** trocar o rótulo, `vision/train/synthgen.
py:256-258` inverte **com** `_flip_case` — semânticas contraditórias (a do `augment` está
desligada; ligá-la ensinaria o oposto do gerador); e `vision/train/finetune.py:265-282` treina
**sem aumento nenhum**, confundidor nunca nomeado da regressão de laboratório do F4 §6.4.

**O que já foi medido e por que se retoma.** `mhsp` 16 ép. (`tronco:docs/EXPERIMENTS_FASE7.md:
989-1016`): 9 casas reparadas contra 15 do controle (−40 %), validação 0,9820 × 0,9790, mesma
exportação 28/38 — reprovado "pela letra do critério" sobre **38 diagramas**; `models/
s40_mhsp_16ep.pt` guardado como "candidato ao próximo retreino". Hoje o campo tem 114 com
placement, 10 negativos anotados, e `lab_gate.py` existe: o instrumento ganhou resolução.
**Hipótese nova nomeada:** `RandomStroke` (erosão/dilatação 1–2 px do glifo; "contorno →
preenchido" só no interior) — o eixo de variação que `hatch/paper/speckle` não cobrem. Não é
o fine-tune sintético rejeitado (dado real + degradação). **Ablação obrigatória**, 3 corridas
cada: `aug0` (produção) × `mhsp` × `mhsp+RandomStroke` × `RandomStroke` sozinho — sem ela o
ganho novo não se isola do já medido. **Medir.** `lab_gate.py --candidate … --runs 3
--unconstrained` (acurácia por casa, exatos, ilegais — a catraca de `EXPERIMENTS_FASE7.md:
918-944`), `field_exact.py --variant recall-pack --corrections` com `export_rate` e
`conditional_exact` ao lado, `evaluate_dataset().top_confusions` para as trocas X↔x,
`style_coverage.py --sets holdout`. Sabotagem: `--augment i` sozinho (inversão sem relabel)
tem de piorar a cor. Dados: `labels.csv` 5.444 linhas (medido), com os 12 do Koblenz e os 80
`transcricao-manual` posteriores ao modelo de 31/08.

### 3.5 D4 — Segunda opinião local (alavanca 18)

`tronco:ui/editor_model.py:289-324` `mark_second_opinion`/`mark_net_corrected` só têm chamador
em testes; `tronco:653f88b` apagou `ui/second_opinion_button.py` (121 linhas) e `ui/net_button.
py`; `tronco:ui/configuracoes.py:116-127` ainda expõe `local_reader.*` e `remote_fen.*`. O que a
S-66 mediu (`ROADMAP_FASE7.md:1493-1503`): Niemeijer, 20 diagramas, confiança mínima média
0,25, zero acima do gate; coerentes com o tema 12/20 local × 18/20 externo; mediana de casas
em desacordo 4,5; nos 3 conferidos à mão o conjunto em desacordo cobriu 4/4, 23/23, 41/41 dos
erros. **Alavanca.** Comando "Segunda opinião" em `qt/painel_de_resultado.py`,
`disputed_squares` pintadas, `corrected_by=segunda-opiniao`. **O segundo leitor tem de ser de
outra família** que o de produção — o clone tsoj (`tsoj_reader.build_local_provider`; 232 MiB,
7 s) ou, se D3 entrar, o `.pt` `aug0` guardado; nunca o irmão `mhsp` do modelo de produção
(a própria sabotagem de D4 é "segundo leitor = cópia do primeiro → cobertura ~0"). **Medir.**
Portão novo: nos 11 barrados de hoje, fração das casas erradas **cobertas** pelo conjunto em
disputa — a régua da S-66; sabotagem: cópia do primeiro. `caissa.ui.audit.comandos` pega a
opção que promete e não faz.

### 3.6 D5 — O sinal por casa atravessa a fronteira (alavanca 11)

`DiagramHit` (`importer.py:164-191`) ganha `square_confidences`, `repairs`, `runner_up` (a
partir de `prediction.square_confidences`, `decode.changed_squares`, `runner_up()` —
`tronco:inference.py:229-241`); a via vetorial preenche 1,0/0,0 por `holes`; `_diagram_node`
(1301-1318) copia para `RecognitionResult` (consumidor pronto: `doubtful_squares()`,
`core/model/diagram.py:201-214`; `export/html.py:2544`). Ordem a1..h8 × a8..h1
(`square_from_reading_index`, `tronco:fen_utils.py:242`). **Medir.** `test_importer`: paridade
`doubtful_squares()` == `uncertain_squares` do tronco; sabotagem: inverter os 64.

### 3.7 D6 — Adaptação por livro do classificador de casas

O que existe para o Tesseract (`ocr/training/books.py`, por hash do PDF) não existe para as
peças; `labels.csv` guarda `source_pdf` por amostra. O erro dominante é cor (§3.1: 10 de 27
casas hoje, 4 delas `q→Q` no Koblenz a 0,71–1,00; F4 §4.2-4.3: 45/86 conjuntos). Duas hipóteses
nomeadas, nenhuma toca o checkpoint e nenhuma é TTA/temperatura: (a) **protótipos por livro**
no embedding de 256-d (`PieceClassifier.classifier[1]`, `tronco:model.py:141-148`) a partir
das casas corrigidas do livro, misturados ao softmax só sob margem top-1/top-2 baixa — mas 4
das 5 casas de cor do Koblenz têm margem **alta** (0,71–1,00), logo (a) sozinha não as pega;
(b) **calibrador de cor por livro**: razão de preenchimento de tinta dentro do glifo com
limiar Otsu por livro, aplicado quando o par (X, x) domina a casa — é o que endereça a
confiança alta. **Medir.** `lab_gate` (não regride) + `f4_field_failures.py --barrados` (as 10
casas de cor, com k = 3, 6, 12 diagramas corrigidos do mesmo livro, **fora das páginas de
campo**); sabotagem: embaralhar os protótipos / o limiar. Custo médio–alto (3–5 dias); é a
única alavanca de diagramas que pede algoritmo, e por isso vem depois das de fiação.

### 3.8 D7 — Coordenadas impressas, ponto de vista das pretas, e um bug vetorial

`CoordinateRule` (`tronco:orientation.py:196-215`) cala em 100 % porque nada constrói
`BoardCoordinates`; a suíte **tem** o leitor (`vision/detect/orientation.py:209-309`,
`orientation_from_labels`) e só o chama na via vetorial (`vector_detect.py:749-757`). Um
diagrama impresso do lado das pretas sai na via raster com FEN girada e confiança alta
(`tronco:inference.py:426-428` admite). E na via vetorial `vector_detect.py:683` **não gira** o
`placement` quando `white_at_bottom=False` (`:737` monta `fen=f"{placement} w…"`), enquanto
`importer.py:230,1322` grava `Orientation.BLACK` e o renderizador vira de novo → exibição
certa, **FEN canônica errada** no PGN/EPUB. População no acervo: **não medida** (S-45 só mediu
o conjunto de campo: 49/49 das brancas). **Alavanca.** `raster_diagram_finder` lê
`_short_labels` + `orientation_from_labels`; girar a FEN (não a imagem); a vetorial gira o
`placement`. **Medir.** Extensão de `vector_survey.py`: linhas de coordenadas em ordem
invertida nos 46 livros — se der zero, resta só o bug vetorial; sabotagem: espelhar os rótulos.

### 3.9 D8 — Restrições que o decodificador não usa, e o lance seguinte como evidência

`tronco:decode.py:103-156` usa reis (=1), peões fora da 1.ª/8.ª, ≤ 8 peões, ≤ 16 peças e o
excesso de promoção (`_promotion_excess`). Não usa: **bispos do mesmo lado em casas da mesma
cor** — não é violação absoluta (promoção), mas consome um peão ausente como o excesso de
promoção já modela; é a dúvida do Stefaniu f1 (C1 §19.2) —, reis adjacentes (`tronco:fen_utils.
py:29-45` classifica como `OPPOSITE_CHECK`, não fatal), balanço de capturas, e **o lance
seguinte** — `games.py`/`side_to_move_gate.py:98-107` já calculam "1.º lance legal a partir da
FEN" e nunca o devolvem à posição (Burgess e5: `...Qxe5` prova a cor da dama). Hoje o decodificador
reparou 14 casas no campo, 10 certas e **4 erradas** (Koblenz `g6`, `g1`; Levenfis `g1`;
Stefaniu `e1`) — 2 delas sobre um `argmax` que já estava certo (Koblenz `g1`, Levenfis `g1`)
e 2 sobre um rei cuja cor o classificador trocou (Koblenz `g6`, Stefaniu `e1`); em 3 das 4 a
violação que ele tentou resolver ("dois reis da mesma cor") nasceu de um rei recolorido, que
ele "resolve" esvaziando ou recolorindo o rei errado — a exceção é o Levenfis (`c3 N→K`) (§3.1). **Alavanca.** (a) as duas
violações novas em `_find_violations`, a dos bispos condicionada a peões ausentes; (b) sinal
"lance seguinte replica" em `DiagramSignals`, e quando falha tentar as `runner_up` das casas
de menor margem até replicar (≤ 2 trocas) — reparo com **evidência externa**, o que contorna
"reparado nunca exporta" sem mentir sobre a probabilidade. **Medir.** (a) `lab_gate`
(`decoder_helped/hurt`); (b) `games_gate` (cobertura 0,04 — população pequena, dizer isso) e
`field_exact` nos livros com `Movetext` legível; sabotagem: alimentar o lance da página vizinha.

### 3.10 Notas menores de diagramas

- Decodificação com restrições corre nas **duas** orientações antes de a política escolher
  (`tronco:page.py:161-171`): 17,7 + 12,7 ms/diagrama nas 10 páginas medidas, e 0,49 s × 2 num
  tabuleiro-lixo (medido nesta análise) — ~15–20 % de `decode_s`, não entrou na tabela.
- Desenhos vetoriais: assinatura desconhecida vira casa vazia (`vector_detect.py:1043-1047`) —
  o defeito que o passo 10 corrigiu para fontes continua nos desenhos; `Diagram.marks` nunca é
  preenchido (o catálogo conhece `marker` e o descarta, `vector_detect.py:324`).
- Setas/destaques/moldura decorativa/3D: 0 diagramas anotados desses estratos (SPEC §11.2) no
  `field_set`. Nota cruzada do explorador de glifos (medido nesta análise, contagem de spans
  Merida no `rawdict`; o survey grava `chess_fonts: []` para esse livro): `400 Quebra-cabeças
  _hq` p.26 tem 47 glifos Merida em 8 linhas de 4–7 e `detect_glyph_boards` devolve 0 —
  casas escuras vazias como retângulo? Verificar antes de contar como lacuna.
- O ciclo corrigir → treinar do tronco não pesa a amostra corrigida (`CrossEntropyLoss` sem
  peso; `corrected_by` nunca lido): 2.242 `ocr-aceito` contra 148 corrigidas à mão (68
  `ocr-corrigido` + 80 `transcricao-manual`), 3.053 sem procedência (medido, `labels.csv`).
- SPEC §6.4 pede que "Mate em 2" seja validável; `importer.py:1317-1329` só preenche
  `stipulation` ("Brancas jogam"/"Pretas jogam"), nunca `Diagram.solution` (`core/model/
  diagram.py:372`), e nada tenta resolver a estipulação — a legalidade da posição de problema
  (`illegal_ok`) é a única checagem. Fica registrado como lacuna sem população anotada
  (nenhum portão a mede); os livros de problemas do acervo (Niemeijer, Polgar) são a população.

---

## 4. OCR de texto

### 4.1 Onde está, recontado por sub-estrato

Os quatro portões de `SOL_REPORT.md` §3 continuam vermelhos no último sistema publicado
(`c1_rapidocr.md`: CER limpo **0,0216** vs 0,005; CER 150 DPI 0,0342 vs 0,020; lances 0,893 vs
0,998; inventados **169** vs 0). O 0,0156 citado em `OCR_UI_ANALISE.md` §3.1 é o de `sol.json`,
**antes** do RapidOCR. Os inventados por estrato abaixo são do `c1_anchor.json` (sistema
"âncora só", total **167**) — dois sistemas, dois totais. Recontagem por sub-estrato do
`c1_anchor.json` (medido nesta análise — o construtor remede):

| estrato | coluna única | problemas | tabela | duas colunas |
|---|---|---|---|---|
| `scan_clean_300` | **0,0052** (101 itens; na meta) | 0,0068 | 0,0023 | **0,1254** (26 itens) |
| `scan_degraded_150` | **0,0127** (< 0,020) | 0,0102 (4 itens) | **0,3016** | 0,0593 |

Lê-se: o "motor único" a que os relatórios atribuem os portões não é a causa dominante —
**leiaute** é. Cinco itens `twocol` com CER > 0,3 respondem por 0,0217 dos 0,0279 do estrato
limpo. O mesmo vale para `moves_invented` (todo lance alterado conta; `ocr/metrics.py:128-138`):
150 DPI 63 (37 coluna única + 26 duas colunas), fax 26, native 25, foto 24, limpo 21, sombra 8
— a massa é substituição de um glifo em lances sem FEN (`Bc4→8c4`, `Kc3→Ke3`, `♘e5→Ae5`), não
o verso espelhado (C1 §1.7), que é real mas pequeno.

### 4.2 T1 — Leiaute na página digitalizada (alavanca 3)

`ocr/page.py:336-354`: PDF de imagem → `analyze_page` sem linhas (`layout/analyze.py:833-835`)
→ `_whole_page` → uma região `PAGE` → `--psm 3` (`tesseract.py:163`). O analisador de leiaute
(colunas por calha, XY-cut, rodapés, legendas) só recebe linhas da camada; `lines_from_result`
(l.256) só aparece em `__all__`. `RegionKind.MOVETEXT` em scan só nasce depois, por estilo
(`paragraphs.tag_movetext`, ≥ 35 %) — por isso o Nunn sai 0/99 no `games_gate` ("os lances
vivem na prosa", C1 §12.1). `c1_rapidocr.md` "Dez piores itens" (l.84-97): **5 dos 10 são `twocol` de
`scan_clean_300`** (d:9, d:4, a:5, a:4, d:18 — todos `accepted` nesse sistema) mais 1 `twocol`
a 150 DPI; a métrica `reading_order` deu 1,0 num item com as colunas intercaladas linha a linha
(cega à intercalação intralinha).

**Alavanca.** Segmentar antes de reconhecer por região, com o que existe: (a) cascata em PSM 3
para obter **caixas de palavra** (palavras não atravessam a calha); (b) `lines_from_result` +
`detect_columns`/`_xy_cut`, ou o detector de calha por projeção do tronco (`tronco:text/
colunas.py detectar_colunas` + `regioes.detectar_regioes`, medidos Nunn 316/352 e Aagaard
28/30 páginas, `colunas.py:20-24`); (c) `LayoutRegion`s de coluna/bloco reconhecidas com PSM
4/6 e o perfil certo — o que também dá `MOVETEXT` em scan e a coluna sob o diagrama (alavanca
5). Variante barata (1 dia): só partir as linhas do Tesseract nas calhas verticais e reordenar
por coluna. **Medir.** `bench_sol.py --strata scan_clean_300,scan_degraded_150 --filter twocol|
table`; `sol_gate` (CER limpo, regressão por estrato em `native`/`scan_clean_300`);
`bench_ingest.py` (colunas vistas e *continuity split* em Nunn/Aagaard); `games_gate.py` p17.
Sabotagem: calha de 0 px → o CER de `twocol` tem de voltar a 0,12. **Risco.** Coluna única
partida por espaço de justificação — o tronco mediu (`LINHAS_NA_CALHA=1`, controle Darcy Lima
0/39); `test_layout.py`.

### 4.3 T2 — O escore da fusão (alavanca 7)

`fusion.py:318-325`: `decide(fused_result, anchor_score, …)` — o escore é o da âncora, nunca
recalculado dos tokens fundidos; 326-338: âncora abstida → no máximo REVIEW; `ocr_service.py:
980-995` (`_settle`): glifos e figurinas nunca ancoram. Sobre os 62 abstidos do estrato
`native` (todos `pdf-scan`, mediana de 11 caracteres — legendas, linhas de lances): 33 têm
secundário aceito/revisão; o melhor secundário sozinho tem CER 0,187 e o fundido descartado
0,22 (medido nesta análise). A abstenção conta como CER 0 (C1 §1.6), então isto é invisível
nos portões.

**Alavanca.** (a) re-pontuar o fundido (`arbiter.score(fused_result)` ou média das confianças
fundidas); (b) regra nova nomeada: "âncora abstida + secundário independente **aceito** com
≥ N tokens de lance concordando com o fundido → REVIEW" (nunca ACCEPTED — preserva SOL-2 e a
lição dos 41 aceitos de 2026-09-14); (c) o modelo do livro registrado pode ancorar quando
`_has_figurines` ≥ 0,70 e a âncora está abaixo do piso de revisão. **Medir.** `bench_sol.py
--strata native --filter real:` (abstidos 62 → ?); `sol_gate` "importação silenciosa" 0 e
"controles" 0/9 (a sabotagem natural); `games_gate` SFC4.

### 4.4 T3/T4 — O que conta como apoio, e três furos de string (alavanca 8)

- `lexicon.py:376-377 _PIECE_LETTERS` é a união de 8 idiomas; `_NOTATION` (394-405) aceita
  `[peça]?[coluna]?[fila]?[x]?casa` → `8c4`, `2c7`, `4a4` são lances; `is_move_token('8c4')
  == True` (medido). Na fusão, `_supported(text, langs)` (353-372) **recebe** `langs` mas só o
  usa para o dicionário, não para `is_move_token` → âncora "apoiada" → nunca substituída
  (`_choose` 514-522), mesmo a 0,0.
- `lexicon.py:384 _LINK_MARKS = "x:×-"` sem `–—‒−`: o Tesseract lê o hífen de LAN como travessão,
  `b2—b4,` não é lance → a fusão o troca pelo `b4,` truncado do leitor de glifos — dois lances
  certos destruídos numa página (medido, `real:Dvoretsky…:17:498:222`).
- `fusion._figurine_cut` (405-431) exige o mesmo prefixo numérico: `17...Ae5` × `7...♘e5` (o
  glifo perdeu o `1`) não troca; `(17...2c7` × `(17...♗c7` o `(` impede; anchor `e5` a 0,21 com
  glifos `♘e5` 1,00 e figurinas 0,97 → "peão não é cifra" (424-427) → nunca substituído.

**Alavanca.** `_supported` passa `langs` a `is_move_token` e só aceita letras de peça de
`fusion._PIECE_LETTERS[langs[0]]` (a tabela por idioma já existe, 83-85), rejeitando
fileira-sem-peça; `measure_evidence` conta esses tokens como `mangled`; `_LINK_MARKS` com
travessões; `_figurine_cut` tira `([` antes de comparar e aceita prefixo do secundário que
seja sufixo do da âncora; regra de **concordância entre secundários independentes** (glifo
torch + figurinas Tesseract) com âncora < 0,35 — hipótese nova, diferente da votação
rejeitada em SOL-6 (aquela era entre variantes ruidosas do *mesmo* motor). Tudo dentro de
R2.2 da `OCR_UI_SPEC.md` (a letra de peça impressa nunca é reescrita) e sem tocar
`caissa.notation.looks_like_move`, cuja permissividade é deliberada (`ASSETS.md` §2.15).
**Medir.** `bench_sol` "lances inventados" (169 → ?) e `native --filter real:` (pdf-scan CER
0,0185 × pdf-native 0,0028, recontado); `notation_integrity --what verdicts` (a camada dos
nativos não pode mudar); `test_fusion.py` com `b2—b4`, `(17...2c7`, `7...♘e5`. Sabotagem:
`langs=()` → a contagem volta ao valor atual.

### 4.5 T5 — O perfil de lances chega à página mista (alavanca 17)

`ocr_service.py:759-777`: `_profile_candidates` só se `region.kind is MOVETEXT or
_looks_like_movetext(result)` (≥ 50 % dos tokens da **página inteira** são lances, 1163-1169)
e `result.engine == "tesseract"`. Numa página de livro digitalizado com prosa e análise a
fração fica sempre abaixo — o DAWG do perfil `PROSE` "corrige" `Nf3` em palavra. **Alavanca,
independente de T1:** para cada linha do Tesseract com `_carries_notation` (`ocr_service.py:
1172-1188`), recortar a faixa e ler com `recognize_with_profile(MOVETEXT)` como candidato de
fusão — o glifo já faz isso por faixa (`recognize_lines`, 953-962). **Medir.** `bench_sol` por
`genre=mixed` (CER 0,0393, lances 0,882 no `c1_rapidocr`) × `movetext`; `s/MP`.

### 4.6 T6 — Escala comum na fusão (alavanca 20)

Aplicar `ArbiterConfig.calibration_for(engine, facet).apply()` às leituras ao montar os `slots`
em `fuse_candidates` (o árbitro está acessível em `_settle`); reajustar os três limiares da
`FusionConfig` na partição `calib` com `calibrate_sol.py` (o procedimento do SOL-4). SOL-4
calibrou o árbitro; SOL-6 nasceu depois e ficou na escala crua — nenhum relatório nota.

### 4.7 T7 — O verso real

`ocr/preprocess.py register_verso` (621-643) e o ramo `ctx.verso` (660-665) estão
implementados; `PortfolioConfig.verso` (`portfolio.py:346`) nunca é preenchido. O importador
tem a página seguinte à mão. **Alavanca.** `verso=render(page±1)` quando `bleed_share ≥
min_bleed_share`; detector de linha espelhada (reconhecer também o `cv2.flip` e comparar apoio
lexical); preferir `bleed_sauvola` como entrada do secundário nessas páginas (C1 §1.7 sugere).
**Medir.** `bench_sol --strata shadow_curl_bleed` (o estrato sintético **é** `cv2.flip` a 0,25 —
`sol_corpus.degrade`); portão de inserção do `sol_gate`.

### 4.8 T8 — Tudo sequencial

`ocr_service.py _recognize_task` (605-622) e `_read_on_variant` (726-755): variantes × motores
× perfis em série; até ~8 invocações de Tesseract por página, overhead fixo 0,10–0,17 s por
chamada (medido); s/MP limpo 1,15 × degradado 6,3 (recontado do `c1_anchor.json`).
`subprocess.run` e o ONNX soltam o GIL: `ThreadPoolExecutor` sobre os candidatos independentes
de uma região, `OMP_THREAD_LIMIT=1`, opcional `tesserocr` residente. E o cancelamento:
`importer.py:605-607 _check_cancel` é por página; uma chamada de Tesseract tem `timeout_s=180`
(`tesseract.py:197`) e não recebe `should_cancel` — passar o gancho ao serviço e matar o
subprocesso ao cancelar. **Medir.** `s/MP` por estrato; igualdade byte a byte do
`ocr_trace.json` (o árbitro exige determinismo); `percurso --fluxo livro` cancelando **dentro**
de uma página (sabotagem: o comportamento atual, que espera a página acabar).

### 4.9 Notas menores de texto

- **Instrumento**: `_xheight_px` (`portfolio.py:117`) filtra componentes por ≤ 0,05·altura da
  imagem; nas páginas sintéticas curtas do corpus (382 px de altura) lê 5 px e a mesma página
  encaixada numa folha de 3.300 px lê 20 px (medido nesta análise: `portfolio.detect_signals` sobre o PNG do item e sobre o mesmo PNG colado numa tela branca A4 a 300 DPI) → todo item "limpo" do
  benchmark é tratado como degradado (roda RapidOCR + upscale) — em produção, com páginas
  inteiras, não dispara. O benchmark mede o que o produto não faz; corrigir e re-baselinar.
- `reading_order` cego à intercalação intralinha; "abstenção = CER 0" esconde T2 — um CER por
  região rotulada seria o portão honesto.
- `TesseractConfig.dpi=300` fixo mesmo em variante a 450–600 (`tesseract.py:196,654`); texto
  OCR emitido sem NFKC (ligadura `ﬁ` do Tesseract entraria no IR; o métrico normaliza e não vê).
- Idioma por documento, fixado para sempre nas primeiras páginas OCR (`importer.py:975-990`);
  nada por página/região/token; página bilíngue não é tratada.

---

## 5. Glifos de xadrez e notação

### 5.1 Onde está

Três leitores (Tesseract, leitor de glifos de 314 classes, `caissa_<livro>` ajustado), a cifra
por livro (Gaprindashvili peça certa 791 → 891/973, C1 §3), o modelo do livro como âncora
dentro do livro (SFC4 `calib` 204/204 figurinas, 281/288 lances, C1 §8). O que este ciclo
achou é *antes* e *depois* dos leitores: a gramática que decide o que é lance, a cadeia de
pré-processamento que o adaptador deixou no tronco, e o caminho até a exportação.

### 5.2 G1 — A cauda do lance e o travessão (alavanca 4)

`notation/legality_repair.py:148 _TRAILING_JUNK = "!?∞±∓⧱⧲□→↑⇆©..."` e `:338 _MOVE_SHAPE` têm
**`⧱⧲` (U+29F1/U+29F2, "error-barred square")** no lugar de **`⩱⩲` (U+2A71/U+2A72)**; faltam
`⨀ ⟳ ∆ †`; e `_MOVE_SHAPE` não aceita os travessões que o mesmo arquivo define em `_DASHES`
(`:143`, `"-‐‑‒–—―−­_"`) embora `ocr/notation/cipher.py:146-147` afirme paridade. `_is_move_like`
(351-366) devolve `False` → `:558-561` "Prose… skipped, not failed" → o lance é pulado e o
replay dessincroniza no seguinte. O mesmo alfabeto estreito em `ocr/lexicon.py:389
_ANNOTATION_MARKS = "+#!?"` (→ `is_move_token("Nf6±") == False`), `fusion.py:79 _MARKS`,
`cipher.py:150-152 _MOVE_BODY` (é a **cauda de anotação** que se alarga, não o alfabeto de
substituição da cifra — anti-padrão 5 do roadmap intacto), `movetext.py:96-108`, e nos
instrumentos `notation_integrity.py:418-419` e `metrics.py:76-81` — que por isso **não veem** a
perda. Medido nesta análise (`.venv\Scripts\python.exe`; o bloco corre como está e afirma os seus
próprios números — saída `ok: …`):

```python
from chess import STARTING_FEN as FEN
from caissa.notation.legality_repair import repair_movetext
from caissa.ingest.pdf.games import game_from_paragraph
from caissa.core.model import Paragraph; from caissa.core.model.inline import Text

r = repair_movetext('1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6⩲ 5.O-O Be7', start_fen=FEN)
assert (len(r.moves), [u.raw for u in r.unresolved]) == (7, ['O-O']), r        # o ⩲ mata o Nf6; com ± → 10
r = repair_movetext('1.e2—e4 e7—e5 2.Ng1—f3 Nb8—c6 3.Bf1—b5 a7—a6', start_fen=FEN)
assert (len(r.moves), r.unresolved) == (0, ()), r                              # travessão: 0 lances, silencioso; com hífen → 6

def plies(g):
    n, out = g, []
    while n.children: n = n.children[0]; out.append(n.san)
    return out, n.comment_after
p = lambda s: Paragraph(content=(Text(content=s),))
for suf in ('±', '⩲'):
    g, why = game_from_paragraph(p(f'1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6{suf} 5. O-O Be7'), FEN)
    sans, tail = plies(g)
    assert (len(sans), tail) == (7, '[não reproduzidos: O-O]'), (sans, tail)   # na via de produto o ± também mata
print('ok: ⩲→7/O-O, travessão→0/(), via de produto ±/⩲→7')
```

**Alavanca.** Uma única classe "cauda de lance" derivada de `nag_table.SEARCHABLE_GLYPHS +
BOOK_SYMBOL_ALIASES` (já é a fonte única do editor), usada nos oito lugares; `_MOVE_SHAPE`
com `_DASHES`; `RepairedMove.suffix` devolvido separado (G5 aproveita); um teste que levanta se
`_TRAILING_JUNK` contiver ponto de código fora da tabela de NAG. **Medir.** `notation_integrity
--what contest` depois de corrigir `_PIECE_MOVE` — sabotagem: acrescentar `±` à verdade dos
lances com peça (hoje o placar não muda, e deveria); `bench_sol` (lances 0,893 sobe; CER não
piora; controles 0/9); `test_legality_repair` com as quatro linhas acima.

### 5.3 G2 — Roque com número colado e formas sem dígito (alavanca 5, parte)

`movetext.py:55 _CASTLING` casa só o token nu e `_is_move` (100-104) não tira o número →
`5.O-O` sai da corrida; `games.py:60 _GLUED_NUMBER` separa `1d4` mas não `5.O-O`;
`legality_repair._is_move_like:366` exige um dígito 1–8 → `OO`, `Qxe4†`, `b8(Q)`, `b8/Q` são
prosa (aliases que `notation/languages.py` declara e o reparador não usa). Medido nesta análise
(mesmo `p(...)`/`plies` de §5.2): `plies(game_from_paragraph(p('1.e4 … 4.Ba4 Nf6 5.O-O Be7 6.Re1
b5 7.Bb3 d6 8.c3 O-O'), FEN)[0])` → 8 lances, `'[não reproduzidos: Be7]'`; com `5. O-O` → 16.
**Alavanca.** Tirar o número antes de `_CASTLING`; `RepairReport.skipped` — um token pulado
**entre dois lances** nunca mais desaparece sem rasto; usar `castling_aliases`/
`promotion_aliases`/`check_aliases` das `LOCALES`. Custo ½ dia.

### 5.4 G3 — O PDF exportado (alavanca 9)

`export/pdf.py:1094-1095` (`piece_glyph`, `move` com `render=FIGURINE`) → `_face` (733-750)
escolhe só roman/bold/italic de `_FALLBACK_FILES` (113-118: `times.ttf`, `georgia.ttf`,
`DejaVuSerif.ttf`, `arial.ttf`); `chess_face` (716-730) só vai ao `_SvgPainter` dos diagramas.
`:1226` e `:1374`: `usable = "".join(c for c in run.text if run.font.has_char(c))` — sem
`context.note`, sem `audit_feature`. Nesta máquina (fontTools, medido nesta análise) nenhuma
das quatro tem U+2654–265F nem ⩲⩱⨁; `seguisym.ttf` tem todos. `export/fidelity.py:396-408`
relê pela sidecar JSON → 100 % com a página sem figurinas. Na mesma família: `export/text.py:
71-110 NAG_SYMBOLS` diverge da `nag_table` (`$22/$23` → `⨁`, que é `$138`; `$44` `=∞` × `©`);
`typeset/figurine.py:64-73 LANGUAGE_LETTERS["ru"] = {K:"К", N:"Ко"}` (as outras duas tabelas
dizem `Кр`/`К`) e é a que `typeset/latex.py:654` usa. **Alavanca.** Face "symbol" em
`_FALLBACK_FILES` com quebra da corrida por face quando `has_char` falha (a infraestrutura de
várias faces por página existe); `recorder.substituted(...)` ao descartar (a fidelidade
declarada passa a contá-lo); `NAG_SYMBOLS` derivado de `nag_table.NAG_BY_CODE`; apagar
`LANGUAGE_LETTERS` e usar `notation_tables.to_language` (ADR-0008). **Medir.** Instrumento novo
pequeno, `tests/unit/export/test_pdf_glyphs.py`: exportar um fixture (`Move` figurina +
`PieceGlyph` + `NagSymbol(14)` + `NagSymbol(22)`) e contar com `pymupdf.get_text()` os pontos
de código contra o IR — reprova se faltar um; sabotagem: trocar `seguisym` por `times`. Base: o
`.notdef` de `test_pdfwrite.py:526-528`.

### 5.5 G4 — A pós-cadeia do tronco (alavanca 14)

`ocr/engines/glyph.py:171-179` importa `binarize, escala_de_texto, caixas_de_caractere,
unir_pingos, ordem_em_faixa, quebrar_em_linhas, descartar_fragmentos`; `read_glyphs`
(247-256) chama `unir_pingos` sem `binaria` e vai direto ao `classificar` (argmax). O tronco
(`text/leitor.py:427-433`) faz `empilhados.unir(..., extras=barras(binaria))` — `empilhados.py:
12-16` mede recall **`:` 9 → 0, `;` 4 → 0, `=` 14 → 0** sem ele, e `g1=♕` saía `g1 ♕` — e
`colados.separar` com árbitro (551-558; `colados.py:14`: sem árbitro custou 2,3 pontos de F1
no projeto de origem), `caixa_alta`, `marca_fina`, `empilhados.corrigir`, `italico`, `numero`,
`dicionario` (574-596). `text/modelo.py margem()` (373-390) é calculada e "nada a usa"; o único
freio da troca é `figurine_min_confidence=0,70`. Só figurinas contorno ♔–♙ (sem ♚–♟); ♙ com
93 amostras; ligaduras com figurina só `♕x ♗x ♗a ♔e ♕f .♗` (`models/char_meta.json`).
**Alavanca.** Chamar `empilhados.unir`, `colados.separar` (só com árbitro), `unir_pingos
(binaria=)`, `empilhados.corrigir`; expor `margem` no `GlyphBox` como segundo critério.
**Medir.** `caissa.ocr.labeling.measure` no SFC4 `calib` (204/204, ≥ 280 lances — o portão já
existe) mais contagem de `=`/`:`/`;` verdade × hipótese; sabotagem: `empilhados` desligado →
recall de `=` volta a 0.

### 5.6 G5 — NAGs na via de importação (alavanca 16)

`games.py:158-178 _move_nodes` nunca preenche `nags`; `book_import.py:670 map_book_symbols`
(²→⩲, ³→⩱, µ→∓, ¹→⌓) só roda ao colar; `textlayer.py:104-125 INFORMATOR_SYMBOLS` emite `⊕ △
⇑ ◻ ◼ −` sem NAG; `nag_table.py:133` `⇆` (U+21C6) sem alias `⇄` (U+21C4), a classe do leitor
de glifos. 6 de 20 símbolos Informator não chegam a `canonical_code` mesmo com
`BOOK_SYMBOL_ALIASES`; 3 classes do leitor não casam (medido). **Alavanca.** `_move_nodes`
extrai o sufixo (`RepairedMove.suffix`, G1) → `nag_table.canonical_code(glyph, white_to_move)`;
`map_book_symbols` nas spans do `textlayer` antes de qualquer NFKC; aliases. **Medir.** Portão
novo nas 6 páginas do DEM pinadas em `notation_integrity`: tokens com sufixo NAG na página ×
`MoveNode.nags` nos `GameScore`; sabotagem: apagar os símbolos do texto → zero.

### 5.7 G6/G7 — Cifra com escopo, `figurine_set`, proveniência do `PieceGlyph`

- `ocr/notation/book_cipher.py:106-121`: qualquer contradição conta para sempre (sem janela nem
  reset); a chave é o símbolo puro, sem estilo (negrito/tamanho — `TextSpan.bold`, `font_size`
  existem): quando o mesmo sósia é ♔ no negrito e ♘ no regular, a linha nunca prova. As trocas
  do glifo entram sem confiança (`ocr_service._observe_glyph_swaps:1057-1094` descarta
  `token.confidence`). Alavanca: chave `(symbol, estilo)` com fallback, janela de contradições,
  exemplos com confiança; medir com `--what contest` (891/973, 346/472, 140/198 não podem cair).
- `importer.py:145-148 _PIECE_OF_GLYPH` dobra ♕ e ♛ na mesma peça e `:1574` constrói
  `PieceGlyph` sem `figurine_set` → padrão `BLACK` (`inline.py:193`) → ♕ contorno sai ♛ sólido
  no DOCX/EPUB (`export/text.py:158-171`). Correção trivial (`WHITE if ch in FIGURINE_WHITE`).
- `inline.py:180-195`: `PieceGlyph` sem `Provenance`; `ocr_service.to_page_text:370-393`
  colapsa a linha num `TextSpan` com a confiança mínima — o `chosen_from="glyph"` fica só no
  `trace()`. A revisão não distingue figurina do leitor (99,1 %) de figurina da cifra (inferida).

### 5.8 Notas menores de glifos

- Fonte de diagrama usada inline apaga a figurina do parágrafo (`textlayer._span_from_dict:
  406-419`; `paragraphs.layout_page:594-600`): risco real de código, população 0 nos 46 livros
  (figurinas inline são SemFig/SkakNew; Merida só em diagramas) — fica registrado, não é passo.
- O leitor de 314 classes: 607.713 recortes, procedência "desconhecida" em 100 %, split por
  cópia exata (não por livro) (`tronco:docs/metrics/texto_treino_20260823_s202.json`); não
  aprende com a bancada (só o Tesseract aprende).

---

## 6. Interface

### 6.1 Onde está

Portões `teclado`, `contraste`, `texto_pintado`, `bloqueio`, `quadros`, `comandos`, `percurso`
(6 ações no livro, 3 por casa), `fita`, `icones` PASSOU (C1 §16–§18); `vazio` REPROVOU (6/8
painéis > 200 kpx a 4K); crítico visual às cegas (C3) pendente. O que este ciclo achou não é
visual: é o **elo final do fluxo** (correção → exportação), o **gesto mais frequente** (ler a
página) sem progresso, e o que nenhum portão mede.

### 6.2 U1 — A correção chega ao livro (alavanca 2)

`export/book.py:339-354`: `_export_book` constrói `PdfImportOptions()` e reimporta; só
`ReviewDecisions.for_pdf(source)` é aplicada; nada lê `labels.csv`, `painel.paginas` nem
`gallery_human.jsonl`. `tronco:qt/importador_de_livro.py:83-84,116` guarda `Ponte.resultado` e
ninguém o lê. E o portão não vê: `ui/audit/percurso.py:263-269` conta "gravar a correção" com
`lambda: True`; 279-292 exporta com `ocr=False` e confere só `destino.exists()` — uma
sabotagem que grave a FEN errada e exporte o mesmo arquivo **passa**. Dois caminhos com regras
diferentes: o botão Exportar do trilho fica desabilitado até importar (`tronco:qt/trilho.py:
207,261`) enquanto `Arquivo ▸ Exportar EPUB` funciona sem importar (`janela.py:1691-1698`).
**Alavanca.** (a) D1; (b) `DiagramDecisions` ao lado de `ReviewDecisions` (`ocr/review.py`):
`(página, bbox) → placement/side`, casado por IoU ≥ 0,5 (o mecanismo de
`_apply_review_decisions`, `importer.py:938-952`), alimentado por `painel_de_resultado.
salvar_atual` e lido em `_export_book`; (c) `export_book` aceita `document=` pronto para
reaproveitar `Ponte.resultado` quando as páginas pedidas ⊆ importadas. **Medir.** `percurso
--fluxo livro`: o passo 5 afirma FEN salva ≠ lida e o passo 6 abre o EPUB (`export/fidelity.py`
já lê EPUB) e exige o `Diagram` corrigido; sabotagem: exportar sem aplicar → reprova.

### 6.3 U2 — Ler a página (alavanca 10)

`tronco:qt/janela.py:1304-1331 _rodar` → `Tarefa(QThread)` sem `should_cancel` nem progresso;
`tronco:service.py:577-585 recognize_page` sem gancho; `tronco:ui/busy.py:251-256` declara
`("janela.py", "_rodar")` em `FORA_DO_REGISTRO` → rodapé sem barra nem Cancelar;
`janela.py:1903-1910` `self.painel.setEnabled(self._tarefa is None)` — o painel Resultado
inteiro cinza. Modelo carregado dentro da primeira leitura (`service.py:536-546`); o
`processo_de_trabalho._aquecer` só importa módulos; sem modelo, `QMessageBox.warning("A leitura
não terminou", "…piece_classifier.pt")` sem dizer o que fazer (`janela.py:1347`). Tempo até o
primeiro resultado a frio: **não medido** por nenhum portão. **Alavanca.** `recognize_page(...,
progress=, should_cancel=)` entre diagramas; `_rodar` no `BusyRegistry` com `total=len
(candidatos)`; trancar só `btn_salvar*`; aquecer o modelo após `abrir_livro_da_sessao`;
`EstadoVazio` com "Ferramentas ▸ Configurações…" quando o `.pt` falta. **Medir.** `caissa.ui.
audit.progresso` passa a exigir `total=` ao tirar `_rodar` de `FORA_DO_REGISTRO`; **modo novo**
`percurso --fluxo casa --frio`: processo novo, sem cache, mede "clique em Ler → primeiro
diagrama na lista" e reprova acima de um teto declarado no roadmap (proposta: 8 s a frio, 3 s
a quente, mediana de 3); sabotagem do tempo: descarregar o modelo a cada clique
(`invalidate_model` antes de `_rodar`) → ultrapassa o teto; sabotagem do cancelamento (no
`--fluxo casa` normal): `should_cancel` ignorado → o portão espera o cancelamento e reprova.

### 6.4 U3 — Tranca seletiva, um só PDF, um só OCR (alavanca 15)

`ui/views/importacao.py:87 controles.emit(False)` → `tronco:qt/janela.py:990-998 _trancar`:
`self.abas.setEnabled(liberado)`; o mesmo para a exportação de livro (527) e PGN/treino
(939-941). `janela.py:463-468` monta Rotulagem e Revisão de texto sem `pdf_inicial`;
`_abriu_livro` (1010-1044) não as avisa; cada uma tem o próprio "Abrir PDF…"
(`ROTULAGEM_aba_no_bundle.png`: Dvoretsky aberto na aba, visor "nenhum livro aberto"). O OCR do
livro roda duas vezes: no trilho (`Ponte`) e na aba (`ImportadorParaRevisao`, `revisao_de_texto.
py:101-170`). **Alavanca.** `_trancar` só para o que compete pelo mesmo recurso; `_abriu_livro`
chama `revisao_de_texto.abrir(alvo)`/`rotulagem.abrir(alvo)`; `Ponte._chegou` entrega
`resultado` à `ReviewQueue.from_import`. **Medir.** **Modo novo** `percurso --fluxo paralelo`
(iniciar importação e, em 1 s, `clicar_na_caixa` + `aplicar` — hoje reprova por widget
desabilitado; sabotagem: o comportamento atual); `test_qt_janela`: abrir PDF →
`revisao_de_texto.pdf == janela._pdf`.

### 6.5 U4 — Desfazer, estado sujo, cache (alavanca 12)

`tronco:ui/historico.py`: pilha de `placement` só; `painel_de_resultado.py:888-897
_trocou_o_lado` não registra; `salvar_todos` e `tirar_caixa` (`janela.py:1492-1517`) fora do
Ctrl+Z. `closeEvent` (1923-1927) pergunta só por `busy.running()`; `has_hand_edits()` só é lido
em `page_results.py:146`. `ui/page_results.py:39,139-157`: LRU de **8 páginas** descarta a 9.ª
**com edições à mão** e um `logger.warning` ("só ficam guardadas quando a amostra é salva").
**Alavanca.** `Historico` guarda `(placement, side)`; `closeEvent`/`_abriu_livro` consultam
`has_hand_edits` e perguntam (a frase e o teste de `_confirmar_fechamento` existem); o LRU não
descarta página editada (ou persiste `PageResults` em `data/janela/<livro>.json`, junto de
U1b). **Medir.** `test_qt_painel_de_resultado` (trocar lado → desfazer devolve);
`test_qt_janela` (editar, `close()` → `ignore()` ao responder Não); teste do LRU com edição —
cada um com a sabotagem sendo o comportamento atual.

### 6.6 U5 — Trilho que aprende, dúvidas navegáveis, teclado no tabuleiro (alavanca 19)

- `tronco:qt/trilho.py:254-263 definir_estados` só por `Ponte._chegou`; `_gravou_amostra`
  (1532-1544), `_fechar_item_da_fila`, decisões de texto não tocam o trilho (§17.5 admite). Só
  `primeira_duvidosa` (282-286; `ui/comandos.py:579`; sem tecla). `ui/trilho.py:112-138`:
  duvidosos = regiões sem decisão + (diagramas − lidos); diagrama lido **com hesitação**
  (`e_duvidoso`, o âmbar do passo 13) não entra.
- `tronco:qt/tabuleiro_editavel.py`/`qt/tabuleiro.py`: sem `setFocusPolicy`, sem
  `keyPressEvent`; só o recorte anda por setas/Enter (`painel_de_recorte.py:85-86,184-207`);
  `paleta_de_pecas.py` sem atalho; `ui/atalhos.py`: 25 teclas (medido), nenhuma para
  K/Q/R/B/N/P, cor, girar, trocar lado, colar FEN. `ui/comandos.py`: 132 `Comando(`, **0** para
  Rotulagem/Revisão de texto; seus `QShortcut` locais (`Ctrl+S`, `Ctrl+O`, `revisao_de_texto.
  py:316-324`) colidem com o `Ctrl+S` global e o portão `comandos` não os vê (só varre o
  catálogo). Estudo: sem entrada de lance por texto ("Nf3").
- **Alavanca.** `atualizar_pagina(pagina, marca)`; `hesitantes` de `DiagramBox.doubtful`;
  `proxima_duvidosa`/`anterior_duvidosa` com tecla; `TabuleiroEditavel.setFocusPolicy
  (StrongFocus)` + `keyPressEvent` (setas/Enter do recorte; `k q r b n p`, Shift = branca,
  Del apaga) → `definir_pincel` + `pressionar`; as ações das abas da suíte como
  `COMANDOS_DA_ABA` (o mecanismo de `sala_declarada`/`texto_declarado`, `janela.py:1788-1791`).
  **Medir.** `percurso --fluxo livro` com N = 2 duvidosas (após gravar a 1.ª, "primeira
  duvidosa" vai à 2.ª — hoje volta à 1.ª); `audit.teclado`, `audit.comandos`; **modo novo**
  `percurso --fluxo casa --teclado`: a mesma correção de casa do `--fluxo casa` feita só com
  `QTest.keyClick` a partir do foco no tabuleiro, contando teclas — reprova acima de 3 por
  casa; sabotagem: tirar o `keyPressEvent` (o fluxo não termina).

### 6.7 U6 — As abas da suíte ignoram a pele

`ui/views/revisao_de_texto.py:312`, `ui/views/rotulagem.py:128-129,234,643,1686,1916`,
`ui/widgets/cartao_da_linha.py:65-67,87,93,109`, `ui/views/exportacao.py:194`: cores Tailwind
cravadas (`#7c3aed`, `#dc2626`, `#3f3f46`, `#111827`, `#6b7280`, `#b45309`), `Consolas` fixa, "◀
anterior"/"próxima ▶" como texto onde o tronco desenha ícones; 27 literais de leiaute contra 8
no tronco (medido). `ui/audit/contraste.py` deriva os pares da folha do tronco
(`pares_da_folha`, 542) — `setStyleSheet` por widget da suíte **não entra**: na Foco (padrão),
`#6b7280` sobre `#1f2124` e `#b45309` sobre escuro estão **não medidos**;
`c18/vazio_passo16_depois.json` mostra a Rotulagem com fundo `#3f3f46` na pele escura. É o item
4/8 da crítica C15 voltando por outra porta. **Alavanca.** As views usam `chess_diagram_ocr.ui.
tokens`/`qt.tema` quando presentes (o padrão de `painel_de_resultado.py:323`) e caem em valores
próprios só sem tronco; `contraste.py` ganha `pares_pintados_da_suite` (a técnica de
`pares_pintados`, 995). **Medir.** `caissa.ui.audit.contraste` ampliado (a sabotagem `sabotar`,
l.1099, já existe).

### 6.8 U7 — Erros que dizem o que fazer

37 `QMessageBox.*` no tronco, nenhum `setDetailedText` (medido); `janela._falhou` (1338-1348)
título fixo "A leitura não terminou"; `Ajuda ▸ abrir_log` só diz onde está o log (1842-1850);
`tronco:ui/estado_do_rodape.py:67-117` infere a severidade por substrings quando quem emite não
a declara (`mostrar(frase, severidade=)` já a aceita — a alavanca é mudar os emissores, não
criar mecanismo); informação expira em 20 s, aviso em 40 s, **erro não expira**
(`EXPIRACAO_MS[ERRO]=None`), e não há histórico do que expirou; `janela.py:168 TITULO_DA_JANELA
= "PyQt"` → barra "… — ChessVisionOFF — PyQt" (visível em `F12_janela_do_bundle.png`), embora
`strings.titulo_da_janela` critique nomear o toolkit. **Alavanca.** `Tarefa.falhou` carrega o
traceback → caixa com `setDetailedText` + "Copiar"; emissores declaram a severidade; lista das
últimas 50 mensagens no rodapé; título sem "— PyQt". Custo ½ dia.

### 6.9 O que nenhum portão mede hoje

- Tempo até o primeiro resultado a frio (U2); conteúdo do arquivo exportado (U1); cancelamento
  dentro de uma página (T8).
- DPI 125–200 % (nenhum portão roda com `QT_SCALE_FACTOR`; `vazio` mede a 4K a 100 %); alto
  contraste do Windows (grep `HighContrast|colorScheme`: nada); leitor de tela no tabuleiro
  ("Casa e2 selecionada" vai ao rodapé sem `QAccessible.updateAccessibility`) — três itens da
  Carta §3.2.
- Os `QShortcut` locais das abas da suíte; a cor dos widgets da suíte (U6).
- **EPUBCheck**: a SPEC §11.3 exige "0 erros" e o `ROADMAP.md` l.64 publica "EPUBCheck 0
  erros" para a F8 — mas a suíte **pula** o teste quando o jar não está na máquina
  (`HANDOFF.md` l.21: "2 pulados: WOFF2/Brotli e EPUBCheck"; `tests/unit/export/corpus.py:31-45`
  procura `CAISSA_EPUBCHECK` ou `%TEMP%`), e o jar não está nesta máquina hoje. O portão
  declarado não roda em nenhuma invariante; entra como invariante do §8 com o jar fixado.
- Validação da estipulação de problema (§3.10, SPEC §6.4).

### 6.10 `vazio`: o que acusa e o que desenhar

`c18/vazio_passo16_depois.json` (escuro): Revisão 3.036 kpx (tabela de 27 linhas em 2.071 px),
Texto 2.016, Revisão de texto 1.842, Estudo 1.512, Galeria 1.488, Rotulagem 756; Dataset 147 e
Resultado 42 passam. Desenho útil: Revisão — cabeçalho fixo, linhas pautadas e rodapé de
contagem, ou lista de cartões com miniatura (é uma fila, não uma planilha); Texto — a
miniatura da página com "Ler folha" (o visor já tem a página); Revisão de texto — o cartão
vazio com os três atalhos e "importar as páginas N–M" pré-preenchido; Estudo — tabuleiro +
lista com "cole um PGN / abra um diagrama" em linha; Galeria — grade com placeholder por página
do trilho. A régua proposta em C1 §16.4 (200 % ou excluir área declaradamente vazia) continua
válida — é o crítico C3 quem decide.

---

## 7. Transversais (o que o Codex viu entre as áreas)

### 7.1 X1 — Identidade diagrama ↔ lances (alavanca 5)

`games.py:249-273` escolhe a âncora geometricamente mais próxima e, sem correspondência,
**devolve `anchors[-1].fen`**; `captions.py` registra `first_move_number` (288, 855, 924) e
`games.py` não o usa para validar. Lances legais a partir do diagrama errado são o pior erro:
plausível e deslocado. **Alavanca.** Relação explícita `diagram_id → movetext_group` com
coluna, bbox, legenda e número esperado do primeiro lance; exigir coerência FEN × paridade ×
primeiro SAN; em dúvida, manter `Movetext` com motivo de revisão, sem `GameScore`. **Medir.**
`games_gate.py` com páginas de duas colunas e âncoras trocadas; sabotagem: trocar dois FENs
legais entre si → zero partidas aceitas com âncora errada, `invented = 0`.

### 7.2 X2 — Quando o OCR de contestação devolve vazio, a camada volta como confiável

`importer.py:823-827`: com `notation_damaged`, `_try_ocr()` que devolve `None` → `"text-layer"`
com a confiança da camada; `_try_ocr` (911-927) captura qualquer exceção e devolve `None` —
a exceção **é** anotada em `report.notes` (`:921`), o resultado **vazio** não. **Alavanca.**
Estado persistente `ocr_attempted/ocr_failed/reason` no bloco; camada acusada + OCR sem
resultado → REVIEW ou imagem, nunca texto aceito. **Medir.** Teste de importação com provedor
que lança ou devolve vazio: o resultado sabotado tem de gerar `REVIEW/ABSTAINED`, nunca a mesma
contagem de texto aceito.

### 7.3 X3 — Perfil de OCR por livro, versionado

`TextLayerThresholds` único (`importer.py:243-310`); `_book_ocr_config()` (890-907) só
especializa `figurine_tessdata`; no tronco `BatchOptions.accept_threshold` único
(`tronco:batch.py:55-65`); `ScanParams` do checkpoint (`tronco:export_checkpoint.py:49-130`)
registra motor/modelo mas não o perfil de limiares. **Alavanca.** `BookOcrProfile` por hash do
PDF (limiares de camada, figurinas, confiança, reparos, lado, aceitação), com o hash gravado em
relatório, checkpoint, fila e exportação — reproduzibilidade, não novo modelo; é o recipiente
de D6. **Medir.** `bench_sol`, `notation_integrity`, `diagram_confidence_gate`, `field_exact`
estratificados por livro; sabotagem: perfil do fax aplicado ao livro limpo → regressão.

### 7.4 X4 — Proveniência que a exportação perde

O PGN do tronco grava `SourcePDF, Page, Diagram, OCRConfidence, SideToMoveSource,
DetectionSource, OCRProblems, OCRRotation` (`tronco:pdf_to_pgn.py:713-751`); o modelo tem
`image_hash`, alternativas, reparos por casa, advertências (`core/model/diagram.py:96-121,
170-215`) que não chegam. **Alavanca.** Sidecar JSONL versionado por chave estável
(jogo/diagrama) com hash da imagem, retângulo, modelo, perfil, confiança por casa, reparos,
decisões humanas; o PGN aponta para ele (aditivo). **Medir.** Exportar/reimportar um item
sintético; sabotagem: dois diagramas com a mesma FEN e proveniências diferentes → colisão
detectada.

### 7.5 X5 — Dar ação aos sinais que a janela já calcula (com a alavanca 11)

`tronco:service.py:97-130,148-179` calcula `changed_squares`, `orientation_ambiguous`,
`orientation_reason`, `side_conflicting`. `painel_de_resultado.py:1184-1203` mostra confiança,
origem do lado, fonte de detecção, legenda e — via `side_source_label(conflicting=)` (1195) —
o rótulo "texto e posição discordam — confira"; **não** mostra as casas que o decodificador
trocou (o `changed` do tabuleiro, `:1134`, é o de `board_edit.differing_squares`, a edição
humana) nem a ambiguidade de orientação. **Alavanca.** Não criar o rótulo que existe: dar-lhe
uma ação (abrir a legenda/os lances que contradizem, trocar o lado); acrescentar os estados
"reparado em N casas" (com as casas pintadas) e "orientação ambígua" (com "comparar as duas"),
cada um com ação. **Medir.** Cenário novo do arnês com `RecognizedDiagram` ambíguo/reparado;
sabotagem: remover os campos → a tela volta à confiança genérica → reprova.

### 7.6 X6 — Fechar o ciclo corrigir → medir → melhorar

`ocr/review.py:289-333` persiste decisões e `corrections()` devolve pares; recalibrar e
retreinar são manuais; no tronco o treino não pesa a amostra corrigida (§3.10). **Alavanca.**
Um comando de fechamento que consome só correções fora da partição cega, gera manifesto de
calibração, atualiza o perfil do livro (X3), registra `model_identity`/hash do documento/versão
do conjunto, e produz relatório antes/depois com aprovação. **Medir.** Fluxo temporário
decisão → manifesto → recalibração → reexecução; sabotagem: decisão de página cega →
`blind_guard()` impede.

### 7.7 X7 — Alt text que afirma o que não foi lido

`importer.py:1276-1310` pode construir um diagrama com `_EMPTY_BOARD` sem FEN; `export/
diagrams.py:216-287` (281-286) gera alt text da FEN atual e assume "jogam as brancas" quando o
lado falta — "tabuleiro vazio, jogam as brancas" para um leitor de tela. **Alavanca.** Alt text
declara "posição não reconhecida", "lado desconhecido", confiança e ID da revisão quando a FEN
é placeholder ou abstida. **Medir.** Teste de exportação com FEN vazia/lado ausente/baixa
confiança; sabotagem: forçar `_EMPTY_BOARD` → o teste exige o aviso.

---

## 8. Ordem sugerida (rascunho para o `OCR_UI_ROADMAP_C2.md`)

Três faixas paralelas, como no ciclo 1; cada passo herda o formato (briefing frio, portão,
sabotagem, "Saída"). Critério de ordem dentro da faixa: primeiro o que **destrava** outro
passo, depois valor/custo, e risco só como desempate. Só a ordem e as dependências, aqui:

```
FAIXA A — fiação e perdas silenciosas (1–2 semanas, 1 construtor)
  A1 alavanca 6 (recall_pack dentro do detector, sem monkeypatch)
     ─► A2 alavanca 1 (raster no produto) ─► A3 alavanca 2 (correção → EPUB; portão do fluxo)
  A4 alavanca 4 (cauda do lance + travessão) ─► A5 alavanca 5 + X1 (roque colado, âncora explícita, skipped)
  A6 alavanca 9 (PDF exportado) · A7 alavanca 12 (LRU/estado sujo/lado) · A8 X2 · A9 X7 · A10 U7
  A11 X4 (sidecar de proveniência — depois de A3, que define a chave por diagrama)
FAIXA B — texto e glifos (2–3 semanas)
  B1 alavanca 3 (leiaute em scan) · B2 alavanca 17 (perfil por faixa — independente de B1; B1 o generaliza)
  B3 alavanca 16 (NAGs) ◄── A4
  B4 alavanca 8 (apoio por idioma, travessão, prefixo) ─► B5 alavanca 7 (escore da fusão) ─► B6 alavanca 20 (escala)
  B7 alavanca 14 (pós-cadeia do glifo) · B8 T7 (verso) · B9 T8 (paralelo + cancelamento dentro da página) · B10 G6/G7
FAIXA C — diagramas e janela (2–3 semanas)
  C1 alavanca 11 + X5 (sinal por casa até a janela e o IR) ─► C2 alavanca 10 (ler a página)
  C3 alavanca 18 (segunda opinião, leitor de OUTRA família) ─► C4 alavanca 13 (mhsp + RandomStroke, com ablação)
     ─► C5 D6 + X3 (calibrador de cor / protótipos por livro, dentro do perfil por livro) ─► C6 X6 (fechar o ciclo)
  C7 alavanca 15 (tranca/um PDF/um OCR) · C8 alavanca 19 (trilho/teclado) · C9 U6 (pele nas abas) · C10 D7 · C11 D8
```

C3 vem **antes** de C4 de propósito: se o `mhsp` virar produção, o segundo leitor não pode ser
o `s40_mhsp_16ep.pt` (irmão do primeiro); C3 fixa o leitor de outra família (tsoj ou o `aug0`
guardado) e C4 não o altera.

Arquivos partilhados que exigem ordem: `importer.py` (A2 → A5 → B1 → A8), `fusion.py` (B4 →
B5 → B6), `games.py` (A5 → B3), `legality_repair.py`/`movetext.py` (A4 → A5),
`painel_de_resultado.py` (C1 → C2 → C3), `export/book.py` (A2 → A3 → A11),
`board_detection.py` (A1 antes de tudo que detecta).

Invariantes depois de todo passo: a suíte de testes; `sol_gate --report-only` (0 importações
silenciosas, 0/9 controles — os três JSON de `sol/` têm 9); `git status --short` só com os
caminhos do passo; e, novidades deste ciclo, **`percurso --fluxo livro` com a asserção sobre
o conteúdo exportado** (A3), que vira o portão do fluxo inteiro, e **EPUBCheck com o jar
fixado por `CAISSA_EPUBCHECK`** (§6.9), para o "0 erros" da SPEC deixar de ser um teste pulado.

---

## 9. O que não refazer

### 9.1 Medido e rejeitado (herdado)

`OCR_UI_ANALISE.md` §6 continua valendo: TTA/jitter, temperatura por casa, `verify_diagram`
por LLM, meia escala, estipulação por LLM, `repair_ocr_region` por LLM, refino de recorte,
decodificação com restrições para `q→Q` (as duas leituras são legais), fine-tune sintético como
está, Surya (licença), ladrilhos no visor (o gargalo era o GIL). Nenhuma alavanca acima os
reabre; D3 nomeia por que o `mhsp` não é o fine-tune sintético e exige ablação; D6 nomeia por
que não é TTA.

### 9.2 O que parecia lacuna e não é (verificado neste ciclo)

- **"CER limpo vem de `ó/6`, `á/4`, `l/1`"** — a coluna única limpa está em 0,0052; a média é
  puxada pelas duas colunas (§4.1). **"150 DPI precisa de super-resolução"** — coluna única a
  0,0127; tabela e duas colunas seguram o portão. SR aprendida fica "não medido, baixo valor"
  até T1.
- Segundo motor não roda em páginas limpas — correto e medido (só o artefato do `_xheight_px`
  no benchmark, §4.9).
- Fusão inserindo tokens / votação de variantes ruidosas; número de lance trocado; âncora
  abstida "certificada" — fechados em SOL-6 e C1 §1.6; T2 pede o caminho oposto (abstida →
  REVIEW), não reverter.
- Tabela de lances no RapidOCR (`_reading_order`, `TABLE_CELL_CHARS`); `user_words`/
  `user_patterns` carregados; whitelist só como candidato extra (correto, destrói prosa).
- Russo com homóglifos latinos (24/24); roque em variantes; `e.p.`, `:`/`×`, `ch`/`mate`;
  promoção `=Q`/`Q`/`=D`/`=♕`; guarda contra reescrever letra de peça impressa (SPEC R2.3);
  leitor de glifos excluindo `rus` de propósito; EPUB embutindo o subconjunto da fonte de
  diagrama; `ignore_diagram_fonts` só na avaliação da camada.
- Moldura dupla (`tighten_board`, tronco `d39b1f1` — §3.1 mostra o efeito); "reparado nunca
  exporta" (custa 1 em 96); gate de exportação ordenando ilegal → ambígua → conflito → xeque →
  confiança; timeout do decodificador; treino da janela protegido por `val_board_exact_acc`;
  S-62a/b (cabeça por tabuleiro) medidos; o rótulo de conflito de lado (§7.5).
- Na interface: rasterização na thread (passo 15); trilho com progresso/cancel e parcial
  aproveitável; `loses_work` no `closeEvent` para operações longas (o buraco é o **estado
  sujo do editor**, U4); nomes acessíveis; `EstadoVazio` em 8 lugares; recorte ∥ tabuleiro;
  geometria multi-monitor; segunda leitura simultânea recusada com frase
  (`tronco:qt/janela.py:1318-1320`); paleta de comandos; botões Qt em português; ícones da
  fita de uma família; cache de ícones por pele.

---

## 10. Decisões que são do usuário, não da análise

1. **Ligar o detector raster na importação/exportação do livro (alavanca 1)** muda o tempo de
   importar um livro não vetorial (0,38 s/diagrama em fluxo único; 300 diagramas ≈ 2 min a mais,
   extrapolado) — aceitar por padrão, ou atrás de uma opção "ler diagramas nas páginas sem
   vetor"?
2. **Retreinar o classificador de produção com `mhsp` (+`RandomStroke`)** substitui o `.pt`
   de 31/08 que passa em todos os portões de laboratório — só com a ablação do §3.4, `lab_gate`
   3× verde e `field_exact` com os três números; quem aprova a troca?
3. **Segunda opinião local**: reativar o clone tsoj (232 MiB, 7 s) ou o `aug0` guardado como
   segundo leitor — nunca o irmão `mhsp` do modelo de produção (§3.5).
4. **Perfil por livro (X3) e adaptação por livro (D6)** criam estado por PDF em `models/` e
   `data/` — aceitável no bundle do usuário (o `--importar-acervo` já funde `data/`)?
5. **Sidecar de proveniência (X4)** ao lado do PGN: sim/não; e onde (mesma pasta, `.json`).
6. **EPUBCheck**: fixar o jar na máquina de referência (`CAISSA_EPUBCHECK`) para o portão
   rodar em toda invariante — hoje é um teste pulado.
7. Continuam pendentes do ciclo 1: 0b (≥ 20 diagramas errados em páginas novas → 8/9/18) e o
   crítico visual C3; o contraste SPEC §13 × Stockfish (`HANDOFF.md` §6.3).

---

## 11. O que a crítica adversarial corrigiu nesta versão

Dois críticos independentes (Claude e Codex), regidos pela `CRITIC_CHARTER.md`, leram a
versão 1.0 contra o código e os relatórios. Ambos **reprovaram** o ciclo 1 (8 + 6 bloqueantes) e
o ciclo 2 (3 + 1); o Claude **aprovou no ciclo 3**; o Codex reprovou o ciclo 3 por 1 (este parágrafo
sem origem) e **aprovou no ciclo 4**. Todos os vereditos estão em
`docs/quality/OCR_UI_ANALISE_C2_CRITICAS.md` (Codex na íntegra; Claude resumido por ciclo). O
que mudou, para que ninguém reaprenda:

| achado (quem) | o que estava escrito | o que o repositório mostra / o que mudou |
|---|---|---|
| `side_conflicting` "não mostrado" (Claude) | X5 propunha criar o estado "texto contradiz posição" | `painel_de_resultado.py:1195` → `strings.py:42` já o mostra; X5 reescrito como "dar ação ao rótulo existente e acrescentar reparado/ambígua" — anti-padrão 12 evitado |
| `recall_pack` sem lock (Claude) | alavanca 1 com custo "baixo" e A1 antes do pacote interno | monkeypatch global (`recall.py:232-318`) numa thread da janela; A1 do §8 passou a ser internalizar o pacote e a alavanca 1 depende dele |
| sabotagem de D2 (Claude) | "desligar `rescue_squares` → 0,9652" | `ROADMAP.md` l.164: 0,9652 é "só resgate"; sabotagem reescrita com as linhas certas (só piso → 0,9478; só multiescala → 0,9826) |
| CER limpo (Claude) | "`c1_rapidocr`: 0,0156" | `c1_rapidocr.md:72` diz 0,0216; 0,0156 é `sol.json` pré-RapidOCR; inventados 167 (âncora) × 169 (RapidOCR) nomeados por sistema |
| "7 de 10 piores são twocol" (Claude) | 7 | `c1_rapidocr.md:84-97`: 5 limpos + 1 a 150 DPI |
| "64/64 nos 3 Niemeijer", "mediana 0,25" (Claude, Codex) | número inexistente | `ROADMAP_FASE7.md:1493-1503`: média 0,25; cobertura 4/4, 23/23, 41/41 |
| Koblenz "8–11 casas de cor" (Claude) | estado anterior a `d39b1f1` | remedido com `f4_field_failures.py --barrados`: 1–4 casas por diagrama, 4 de 7 `q→Q` a 0,71–1,00 pelo classificador + 1 recolorida pelo decodificador; tabela nova no §3.1 |
| C3 (mhsp) → C4 (segundo modelo `mhsp`) (Claude) | ordem que faz o segundo leitor ser irmão do primeiro | segunda opinião antes do retreino e de outra família; §10.3 corrigido |
| SOL-7 "nunca roda em scan" (Codex) | absoluto | `ocr_service.py:775`: `kind is MOVETEXT or _looks_like_movetext` (≥ 50 % da página); reescrito como "nunca numa página mista" |
| medição de `game_from_paragraph` com assinatura inválida (Codex) | chamada com string | reproduzida com `Paragraph(content=(Text(content=…),))` e `start_fen`; comandos no §5.2/§5.3; a via de produto perde também com `±` |
| números sem origem (Codex, Claude) | 5.444, 38, 314, 2,3 F1, 289≈20 min, 25 teclas, 382/5 px, 2.158 Merida | cada um com relatório§, arquivo:linha ou marca "(medido)"/"(extrapolado)" |
| `--frio`/`--teclado`/`--paralelo` inexistentes (Codex) | citados como se existissem | declarados como modos novos do `percurso` com o que medem, o teto e a sabotagem |
| "não repete nada" × `mhsp` (Codex) | afirmação absoluta | cabeçalho e §3.4 reescritos: retoma a S-40 com hipótese nova e ablação obrigatória |
| EPUBCheck e estipulação (Codex) | ausentes | §6.9 (portão declarado que é teste pulado) e §3.10 (`solution` nunca preenchido) |
| travessão em `_MOVE_SHAPE` (Claude, achado novo) | não constava | `repair_movetext('1.e2—e4 …') → 0 lances, unresolved=()`; entrou na alavanca 4 e em §2.3 |
| cancelamento por página (Claude, achado novo) | não constava | `importer.py:605-607`, `tesseract.py:197`; entrou na alavanca 10 e em T8 |
| linhas/arquivos imprecisos (Claude) | `_settle` em `fusion.py`, `games.py:57`, `importacao.py:92`, `fen_utils.py:114-152`, `barrados.md l.6-9`, `SignatureIndex.learn_from_board` | corrigidos para `ocr_service.py:980-995`, `:60`, `:87`, `:29-45`, `propostas_0b.md:14`, função de módulo `learn_from_board` |
| X2 "falha silenciosa" (Claude) | exceção e vazio | a exceção é anotada em `report.notes` (`:921`); só o vazio é silencioso |
| U7 severidade/expiração (Claude) | "severidade por palavra-chave; expira em 20/40 s" | `mostrar(frase, severidade=)` já existe; erro não expira; alavanca = mudar emissores |
| "0/12 controles" (Claude) | frase herdada do roadmap | os JSON de `sol/` têm 0/9 |
| §8 sem X3/X4/X6; B1→B2 contradizia T5 (Claude) | — | X4 em A11, X3/X6 em C5/C6; B2 independente de B1 |
| **ciclo 2** — "as 4 casas que o decodificador reparou estão todas erradas" (Claude) | leitura errada do `failures.json` | `totals.repaired_squares = 14` em 7 diagramas, 10 certas, 4 erradas; 3 das erradas partem de um rei recolorido — §3.1 e §3.9 reescritos |
| ciclo 2 — Koblenz "5 de cor a 0,71–1,00" (Claude) | misturava classificador e decodificador | `g1 K→k` é reparo do decodificador sobre `K` a 0,48; "de cor" definido (10 na leitura final, 11 pelo `argmax`); D6 diz "4 das 5" |
| ciclo 2 — "289 páginas ≈ 17 min" (Claude) | aritmética | 289 × 31,9 / 8 = 1.152 s ≈ 19 min |
| ciclo 2 — sabotagem do `--frio` não tocava o tempo (Claude) | anti-padrão 2 | sabotagem própria: descarregar o modelo a cada clique |
| ciclo 2 — bloco do §5.2 usa `FEN` sem defini-lo (Codex) | `NameError` ao executar literalmente | `from chess import STARTING_FEN as FEN` na 1.ª linha; bloco reexecutado como publicado |
| ciclo 3 — "8 + 6 bloqueantes" sem origem (Codex) | número sem fonte | vereditos gravados em `docs/quality/OCR_UI_ANALISE_C2_CRITICAS.md` |
| ciclo 3 — bloco do §5.2 silencioso; `c1_rapidocr.md:84-96` (Codex) | sem `print`/`assert`; a 5.ª linha `twocol` está em l.97 | bloco com `assert` e `print('ok…')`; `84-97` |
| ciclo 3 — §3.9 "3 delas … ou" (Claude, não bloqueante) | disjunção cobria as 4 | reescrito: 2 sobre `argmax` certo, 2 sobre rei recolorido; em 3 das 4 a violação nasceu de um rei recolorido |
