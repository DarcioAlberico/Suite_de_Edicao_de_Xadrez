# OCR/UI — roadmap do ciclo 2

> **Data:** 2026-09-20 · **Fonte:** `docs/OCR_UI_ANALISE_C2.md` (aprovada pelos críticos; §0 =
> as 20 alavancas, §8 = a ordem). Este documento detalha a **fase 1** (fiação e perdas
> silenciosas) com o formato do ciclo 1 — briefing frio, arquivos, portão, sabotagem, "Saída" —
> e lista as fases 2 e 3 por alavanca, a detalhar quando a 1 fechar. Relatório do construtor:
> `docs/quality/OCR_UI_REPORT_C2.md` (uma seção por passo, todo número com o comando ao lado).
> Não substitui `OCR_UI_ROADMAP.md` (ciclo 1), cujas pendências humanas (0b, crítico C3) continuam.
> **Fase 2** (§3) executada em 2026-09-20/21 — relatório `docs/quality/OCR_UI_REPORT_C2_FASE2.md`.

## 0. Regras que valem para todos os passos

- **Ambientes.** Suíte: `.venv\Scripts\python.exe` (3.11; pytest). Testes PyQt6 da suíte:
  `PYTHONPATH=.venv-pack\Lib\site-packages .venv\Scripts\python.exe -m pytest tests\unit\ui`.
  Tronco: `..\ChessVisionOFF_Puro\.venv\Scripts\python.exe -m pytest` (3.10; **não importa
  `caissa`** sem `PYTHONPATH`). Portões da F9 (`caissa.ui.audit.*`): a receita de
  `OCR_UI_ROADMAP.md` §0 (`QT_QPA_PLATFORM=offscreen`, `PYTHONPATH=<suite>\src;<tronco>\src`,
  `.venv-pack`).
- **Invariantes depois de todo passo:** `pytest tests -q -p no:cacheprovider --ignore=tests\
  integration\test_packaging.py --ignore=tests\unit\model\test_roundtrip_corpus.py` (e este à
  parte) — com `PYTHONPATH=.venv-pack\Lib\site-packages` para os `test_*_view.py` (que importam
  PyQt6 no topo) e, nesse caso, `tests\unit\ui\test_arquitetura.py` **à parte** (afirma que nenhum
  binding de Qt está em `sys.modules`, o que é falso por ordem depois dos testes de janela); testes do tronco; `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json`
  (0 silenciosas, 0/9 controles) quando o passo toca `caissa.ocr`; `git status --short` só com os
  caminhos do passo.
- **Commits por caminho nomeado**, nunca `git add -A` (outra sessão trabalha neste checkout).
  Tronco e suíte são repositórios distintos: um commit em cada, o hash do outro na mensagem.
- **Portão novo só com sabotagem executada** que o faça reprovar; número só com comando.
- **Anti-padrões** de `OCR_UI_ROADMAP.md` §5 continuam proibidos (rótulo em `toolTip()`,
  alargar o alfabeto de substituição da cifra, editar `field_set.jsonl`, criar o que existe…).
- Uma correção humana **nunca** entra na partição cega (`blind_guard`).

## 1. Contratos partilhados da fase 1 (definidos aqui para os pacotes andarem em paralelo)

### 1.1 `caissa.ocr.diagram_decisions` (novo módulo, suíte) — passo A3

```python
@dataclass(frozen=True, slots=True)
class DiagramDecision:
    page_index: int            # 0-based, como ReviewDecisions
    rect: tuple[float, float, float, float]   # page.rect em PONTOS (x0, y0, x1, y1)
    fen: str                   # FEN completa (placement + lado + roque + ep + contadores)
    side: str                  # "w" | "b"
    decided_at: str            # ISO-8601 UTC
    reviewer: str = ""
    source: str = "janela"     # quem gravou: "janela" (tronco), "rotulagem", ...
    note: str = ""

class DiagramDecisions:
    items: tuple[DiagramDecision, ...]
    def add(self, decision) -> "DiagramDecisions"        # substitui a decisão da mesma (página, rect IoU ≥ 0,5)
    def match(self, page_index, rect, *, iou=0.5) -> DiagramDecision | None
    def apply(self, hit: DiagramHit, page_index) -> DiagramHit   # devolve o hit com fen/orientação da decisão e method="human"
    def save(self, path) -> Path ; @classmethod load(path) ; @classmethod for_pdf(pdf_path) -> DiagramDecisions | None
def decisions_path(pdf_path) -> Path   # labeling/diagramas/<mesmo slug que ReviewDecisions>.json
def record(pdf_path, decision) -> Path  # carrega-ou-cria, add, save — a função que o tronco chama
```

`PdfImportOptions.diagram_decisions: Any | None = None`; `PdfImporter` carrega-as em
`_diagram_node` (IoU ≥ 0,5 sobre `hit.box`) e o `Diagram` sai com `fen` da decisão,
`provenance.verified_by_human=True`, `recognition.fen` = a leitura da máquina (o par que o
docstring de `RecognitionResult.fen` promete). `export_book` carrega `DiagramDecisions.for_pdf
(source)` como já faz com `ReviewDecisions`. O tronco chama `record(...)` quando o revisor grava
uma posição (só se `caissa` estiver importável — a mesma guarda das abas da suíte).

### 1.2 Sinal por casa em `DiagramHit` — passo C1

```python
square_confidences: tuple[float, ...] = ()     # 64 valores, índice 0 = a1 … 63 = h8 (a ordem de RecognitionResult.per_square_confidence)
repairs: tuple[SquareRepair, ...] = ()         # core.model.diagram.SquareRepair (casa, de, para)
alternatives: tuple[FenCandidate, ...] = ()    # runner-up por casa embalado como FenCandidate quando fizer sentido; pode ficar vazio
model_hash: str = ""
orientation_ambiguous: bool = False
orientation_reason: str = ""
```

A via raster preenche a partir de `prediction.square_confidences` (ordem de leitura a8..h1 →
converter com `square_from_reading_index`), `decode.changed_squares`, `runner_up()`; a via
vetorial preenche 1,0 por casa e 0,0 nos `holes`. `_diagram_node` copia para
`RecognitionResult`. Teste de paridade: `doubtful_squares()` == `uncertain_squares` do tronco.

### 1.3 `RepairReport.skipped` e `RepairedMove.suffix` — passos A4/A5

`RepairReport.skipped: tuple[Skipped, ...]` com `(raw, ply, reason)` para todo token pulado como
prosa **entre dois lances**; `RepairedMove.suffix: str` com a cauda de anotação separada
(`±`, `⩲`, `!?`, …) para o passo B3 (NAGs) da fase 2.

## 2. Fase 1 — os passos

Formato: **arquivos** · **briefing** · **portão** · **sabotagem** · **saída**. "Análise §x" refere
`OCR_UI_ANALISE_C2.md`.

### A1 — `recall_pack` dentro do detector (alavanca 6; análise §3.3)

- **Arquivos.** Tronco: `board_detection.py` (`detect_boards`/`_extract_candidate_quads` ganham
  as recuperações como opção — multiescala somando, resgate de quadrado — com um `RecallOptions`
  em `config.py` ligado por padrão), `detection/hybrid.py` (`candidates_from_embedded_images
  (page, checker_floor=...)`, piso por padrão). Suíte: `vision/detect/recall.py` vira wrapper fino
  (mantém `recall_pack()` como *context manager* que só fixa a opção do tronco — os benchmarks
  continuam a funcionar), `ingest/pdf/finders.py` deixa de monkeypatchar.
- **Briefing.** Portar a lógica de `recall.py:206-338` para o tronco (que não importa `caissa`),
  sem trocar globais; a janela e a suíte passam a chamar a mesma função. Nada de `global` nem de
  troca de atributo de módulo.
- **Portão.** `benchmarks\validate_detection.py` e `benchmarks\field_exact.py --variant baseline`
  coincidem com `recall-pack`: recall **0,9913**, precisão **1,0000** (mediana de 3).
  `profile_detection.py` antes/depois (o custo do passe extra fica registrado).
- **Sabotagem.** `RecallOptions(multiscale=False, rescue=False)` → recall 0,9478; só multiescala
  → 0,9826 (a tabela de `ROADMAP.md` l.157-166).
- **Saída.** Tronco + suíte commitados; §A1 do relatório com os três números.

### A2 — Diagrama raster na importação e na exportação (alavanca 1; análise §3.2)

- **Arquivos.** Suíte: `ui/views/importacao.py`, `ui/views/exportacao.py`, `export/book.py`,
  `ingest/pdf/finders.py` (`combined_finder(classifier=…)`), `vision/classify/residency.py`
  (`acquire_square_classifier` passa a ter chamador: um classificador por processo, partilhado).
- **Briefing.** Depois de A1. `PdfImportOptions.diagram_finder` padrão do produto =
  `combined_finder()`; opção `detect_raster_diagrams: bool = True` para desligar. O classificador é
  carregado uma vez por sessão (`acquire_square_classifier`), nunca por chamada.
- **Portão.** `caissa.ui.audit.percurso --fluxo livro` ganha a asserção "diagramas ≥ 1 num livro
  não vetorial" (Aagaard p.31–38: hoje 0); `benchmarks\bench_ingest.py --raster --sample 4`
  (tempo por página antes/depois).
- **Sabotagem.** `detect_raster_diagrams=False` → 0 diagramas → REPROVA.
- **Saída.** §A2: diagramas por página no Aagaard, tempo por página.

### A3 — A correção da janela chega ao EPUB/DOCX (alavanca 2; análise §6.2)

- **Arquivos.** Suíte: `ocr/diagram_decisions.py` (novo, contrato §1.1), `ingest/pdf/importer.py`
  (`PdfImportOptions.diagram_decisions`, aplicação em `_diagram_node`), `export/book.py`
  (`for_pdf`; `export_book(document=…)` para reaproveitar um `ImportResult` pronto),
  `ui/audit/percurso.py` (o fluxo `livro` passa a afirmar conteúdo: FEN salva ≠ lida e o EPUB
  contém o `Diagram` corrigido — `export/fidelity.py` lê EPUB), testes. Tronco:
  `qt/painel_de_resultado.py`/`qt/janela.py` — ao gravar (`_gravar_alvo` com sucesso), chamar
  `caissa.ocr.diagram_decisions.record(pdf, DiagramDecision(...))` com o rect em **pontos**
  (bbox em px × 72/dpi do render); `qt/importador_de_livro.py` guarda `Ponte.resultado` e a
  exportação pelo trilho passa `document=` quando as páginas pedidas ⊆ importadas.
- **Portão.** `percurso --fluxo livro` PASSOU com a asserção de conteúdo; teste unitário
  `tests/unit/export/test_book_decisions.py` (decisão gravada → EPUB com a FEN corrigida).
- **Sabotagem.** `--sabotar sem_decisao` (exportar sem aplicar) → REPROVA.
- **Saída.** §A3.

### A4 — A cauda do lance e o travessão (alavanca 4; análise §5.2)

- **Arquivos.** Suíte: `notation/legality_repair.py` (`_TRAILING_JUNK`, `_MOVE_SHAPE` com
  `_DASHES` e a tabela de NAG; `RepairedMove.suffix`), `ocr/lexicon.py` (`_ANNOTATION_MARKS`),
  `ocr/fusion.py` (`_MARKS`, `_supported`, `_figurine_cut`), `ocr/notation/cipher.py`
  (`_MOVE_BODY` — cauda, não alfabeto), `ocr/notation/movetext.py` (`_is_move`),
  `ocr/metrics.py` (`MOVE_TOKEN`), `benchmarks/notation_integrity.py` (`_PIECE_MOVE`);
  uma fonte única (`notation/nag_table.SEARCHABLE_GLYPHS + BOOK_SYMBOL_ALIASES`) exposta como
  `notation.nag_table.MOVE_SUFFIX_CHARS` (ou nome equivalente) e um teste que levanta se algum
  destes alfabetos contiver ponto de código fora dela.
- **Portão.** O bloco do §5.2 da análise passa a dar `Nf6⩲` → 8 lances, travessão → 6; `bench_sol
  --strata native,scan_clean_300` lances ≥ 0,893 e CER sem regressão fora do IC; `notation_integrity
  --what contest` sem queda de "peça certa"; controles 0/9.
- **Sabotagem.** Acrescentar `±` à verdade dos lances com peça no `notation_integrity` — o placar
  tem de mudar (hoje não muda).
- **Saída.** §A4.

### A5 — Roque com número colado, âncora explícita, `skipped` (alavanca 5, X1; análise §5.3, §7.1)

- **Arquivos.** Suíte: `ocr/notation/movetext.py` (`_is_move` tira o número antes de
  `_CASTLING`), `ingest/pdf/games.py` (`_GLUED_NUMBER` cobre `O-O`; **sem** `anchors[-1].fen` —
  sem correspondência geométrica devolve `(None, "sem diagrama âncora")` e o parágrafo fica
  `Movetext` com motivo; usa `first_move_number` da legenda/coluna para exigir paridade com a
  FEN), `notation/legality_repair.py` (`RepairReport.skipped`; `_is_move_like` aceita
  `castling_aliases`/`promotion_aliases`/`check_aliases` das `LOCALES`), `benchmarks/games_gate.py`
  (`--sabotar ancora`: trocar dois FENs legais entre si → 0 partidas com âncora errada).
- **Portão.** `games_gate.py` SFC4: `invented = 0`, cobertura ≥ a de hoje (0,04) e **nenhuma**
  partida com âncora errada na sabotagem; `tests/unit/ocr/test_movetext.py` com `5.O-O`.
- **Sabotagem.** `--sabotar ancora` (acima).
- **Saída.** §A5.

### A6 — O PDF exportado com figurinas e símbolos (alavanca 9; análise §5.4)

- **Arquivos.** Suíte: `export/pdf.py` (face "symbol" em `_FALLBACK_FILES` — `seguisym.ttf`,
  `DejaVuSans.ttf`, `NotoSansSymbols2` — com quebra da corrida por face quando `has_char`
  falha; `context.recorder.substituted(...)` ao descartar), `export/text.py` (`NAG_SYMBOLS`
  derivado de `nag_table.NAG_BY_CODE`), `typeset/figurine.py` (`LANGUAGE_LETTERS` apagado →
  `notation_tables.to_language`), `typeset/latex.py`, testes `tests/unit/export/test_pdf_glyphs.py`.
- **Portão.** Fixture (`Move` figurina + `PieceGlyph` + `NagSymbol(14)` + `NagSymbol(22)`)
  exportado para PDF; `pymupdf.get_text()` contém todos os pontos de código do IR; LaTeX `ru`
  imprime `Кр`/`К`.
- **Sabotagem.** `_FALLBACK_FILES` sem a face symbol → o teste reprova (e a fidelidade declarada
  passa a contar a substituição).
- **Saída.** §A6.

### A7 — Desfazer o lado, estado sujo, cache que não perde (alavanca 12; análise §6.5)

- **Arquivos.** Tronco: `ui/historico.py` (`(placement, side)`), `qt/painel_de_resultado.py`
  (`_trocou_o_lado` registra), `ui/page_results.py` (LRU não descarta página com
  `has_hand_edits`; ou persiste), `qt/janela.py` (`closeEvent`/`_abriu_livro` consultam
  `has_hand_edits` e perguntam), testes `tests/test_qt_painel_de_resultado.py`,
  `tests/test_qt_janela.py`, `tests/test_page_results.py`.
- **Portão.** Os três testes, cada um com a sabotagem = comportamento atual afirmada num teste
  invertido que reprova.
- **Saída.** §A7.

### A8 — OCR de contestação vazio não vira camada confiável (X2; análise §7.2)

- **Arquivos.** Suíte: `ingest/pdf/importer.py` (`_try_ocr` devolve um resultado com estado
  `ocr_attempted/ocr_failed/reason`; camada acusada + OCR sem resultado → página em
  REVIEW, nunca `"text-layer"` com a confiança da camada), `tests/unit/ingest/test_importer.py`.
- **Portão.** Teste com provedor que lança e com provedor que devolve vazio: contagem de texto
  aceito **menor** que a da rodada normal; `report.notes` nomeia a página.
- **Saída.** §A8.

### A9 — Alt text que não afirma o que não foi lido (X7; análise §7.7)

- **Arquivos.** Suíte: `export/diagrams.py` (alt text "posição não reconhecida" / "lado
  desconhecido" quando a FEN é `_EMPTY_BOARD`/abstida ou o lado não tem origem), testes.
- **Portão.** Teste de exportação com FEN vazia, lado ausente, confiança baixa.
- **Sabotagem.** Forçar `_EMPTY_BOARD` → o teste exige o aviso.
- **Saída.** §A9.

### A10 — Erros que dizem o que fazer (U7; análise §6.8)

- **Arquivos.** Tronco: `qt/janela.py` (`_falhou` com `setDetailedText` + botão "Copiar";
  `TITULO_DA_JANELA` sem "PyQt"), `qt/trabalho.py` (`Tarefa.falhou` carrega o traceback),
  `ui/estado_do_rodape.py` + emissores (severidade declarada; lista das últimas 50 mensagens),
  testes.
- **Portão.** Teste de janela que injeta `Tarefa` falhando e afirma `detailedText` não vazio;
  `caissa.ui.audit.texto_pintado`/`teclado` continuam PASSOU.
- **Saída.** §A10.

### B4 — O que conta como apoio; travessão; prefixo (alavanca 8; análise §4.4)

- **Arquivos.** Suíte: `ocr/lexicon.py` (`_LINK_MARKS` com `–—‒−`; `is_move_token(text, langs)`
  só com letras de peça do idioma), `ocr/fusion.py` (`_supported` passa `langs`; `_figurine_cut`
  tira `([` e aceita prefixo-sufixo; concordância entre secundários independentes com âncora
  < 0,35), `ocr/decision.py` (`measure_evidence` conta fileira-sem-peça como `mangled`), testes
  `tests/unit/ocr/test_fusion.py` (`b2—b4`, `(17...2c7`, `7...♘e5`, `8c4`).
- **Portão.** `bench_sol.py --system sol --strata native --filter real:` (CER pdf-scan 0,0185 →
  menor; lances ↑) e `--strata native,scan_clean_300,fax_dither` (inventados 169 → menor; nenhuma
  regressão fora do IC; controles 0/9); `notation_integrity --what verdicts` sem mudança nos
  nativos.
- **Sabotagem.** `langs=()` → a contagem volta ao valor atual.
- **Saída.** §B4.

### B7 — A pós-cadeia do tronco no leitor de glifos (alavanca 14; análise §5.5)

- **Arquivos.** Suíte: `ocr/engines/glyph.py` (`empilhados.unir(..., extras=barras(binaria))`,
  `colados.separar` **com árbitro**, `unir_pingos(binaria=)`, `empilhados.corrigir`; `GlyphBox.
  margin` exposto e usado como 2.º critério em `fusion._figurine_cut`), testes.
- **Portão.** `caissa.ocr.labeling.measure` no SFC4 `calib`: figurinas ≥ 204/204, lances ≥ 280
  (portão existente) **e** recall de `=`/`:`/`;` verdade × hipótese > 0 (hoje 0).
- **Sabotagem.** `empilhados` desligado → recall de `=` volta a 0.
- **Saída.** §B7.

### C1 — O sinal por casa atravessa a fronteira e vira estado com ação (alavanca 11, X5; análise §3.6, §7.5)

- **Arquivos.** Suíte: `ingest/pdf/importer.py` (`DiagramHit` — contrato §1.2 — e
  `_diagram_node`), `ingest/pdf/finders.py` (raster e vetorial preenchem), `tests/unit/ingest/
  test_importer.py` (paridade com `uncertain_squares`). Tronco: `qt/painel_de_resultado.py`
  (estados "reparado em N casas" com as casas pintadas, "orientação ambígua" com "comparar as
  duas", e ação no rótulo de conflito de lado já existente), `ui/strings.py`, testes Qt.
- **Portão.** Teste de paridade; cenário do arnês (`tests/test_qt_painel_de_resultado.py`) com
  `RecognizedDiagram` ambíguo/reparado → os três estados aparecem com ação; `contraste`,
  `teclado`, `texto_pintado` PASSOU.
- **Sabotagem.** Remover os campos do modelo → a tela volta à confiança genérica → o teste reprova;
  inverter os 64 índices → paridade reprova.
- **Saída.** §C1.

### C7 — Tranca seletiva, um só PDF, um só OCR (alavanca 15; análise §6.4)

- **Arquivos.** Tronco: `qt/janela.py` (`_trancar` só o que compete pelo recurso; `_abriu_livro`
  avisa Rotulagem e Revisão de texto), `qt/importador_de_livro.py` (`Ponte._chegou` entrega o
  `ImportResult` à aba de revisão). Suíte: `ui/views/revisao_de_texto.py` (`abrir(pdf)`,
  `receber_importacao(result)` → `ReviewQueue.from_import`), `ui/views/rotulagem.py` (`abrir`),
  `ui/audit/percurso.py` (`--fluxo paralelo`: iniciar a importação e, em 1 s, `clicar_na_caixa`
  + `aplicar`), testes.
- **Portão.** `percurso --fluxo paralelo` PASSOU; `test_qt_janela`: abrir PDF → a aba de revisão
  tem o mesmo PDF; o OCR do livro roda uma vez (contador no `Ponte`).
- **Sabotagem.** O comportamento atual (`abas.setEnabled(False)`) → REPROVA.
- **Saída.** §C7.

## 3. Fase 2 — texto, glifos e janela (executada em 2026-09-20/21)

Mesmo formato da fase 1: **arquivos** · **briefing** · **portão** · **sabotagem** · **saída**. O
relatório é `docs/quality/OCR_UI_REPORT_C2_FASE2.md` (uma seção por passo, número com comando ao
lado). Construída por uma sessão só, passo a passo, com os benchmarks rodados **em sequência** (a
primeira rodada, feita em paralelo com testes, contaminou o `s/MP` e foi descartada — §4).
Tronco: commit **2077410**; suíte: o commit que traz esta seção.

### B1 — Leiaute na página digitalizada (alavanca 3; análise §4.2)

- **Arquivos.** Suíte: `ocr/layout/scan.py` (novo: `find_gutters`, `split_at_gutters`,
  `scan_layout`, `ScanLayoutConfig`), `ocr/page.py` (`PageConfig.scan`/`scan_reread`;
  `_whole_page` → `_scan_layout`/`_by_scan_layout`; `_crop` aceita caixa em pixels na tarefa sem
  PDF), `benchmarks/bench_sol.py` (`SOL_CONFIG` aninhado: `{"page": {"scan": {...}}}`),
  `tests/unit/ocr/test_scan_layout.py`.
- **Briefing.** O método do tronco (`text/colunas.py`, projeção de **linhas** feitas de caixas de
  **palavra**, uma linha tolerada na calha a partir de 12, piso de 0,8 caractere/1 %/4 px, faixa
  estreita fundida) sobre a leitura inteira em PSM 3; as linhas partidas nas calhas vão ao
  `analyze_page` de sempre; região de lances → `MOVETEXT`. **Duas guardas medidas** (§4): três
  faixas = tabela (`max_columns=2`); faixa com mediana < 16 caracteres = lista de lances
  (`min_band_chars`). `scan_reread=False` por medição: fatiar a leitura inteira dá CER 0,0111 em
  42,5 s contra 0,0206 em 66,3 s relendo por região (26 itens `twocol`).
- **Portão.** `bench_sol --strata scan_clean_300,scan_degraded_150,native`: CER `twocol`
  0,1238 → ≤ 0,012; `scan_clean_300` inteiro sem regressão fora do IC; `table` e `single`
  inalterados; controles 0/9.
- **Sabotagem.** `SOL_CONFIG='{"page": {"scan": {"enabled": false}}}'` → `twocol` volta a 0,12.
- **Saída.** §B1 do relatório.

### B2 — O perfil de lances chega à página mista (alavanca 17; análise §4.5)

- **Arquivos.** Suíte: `ingest/pdf/ocr_service.py` (`OcrServiceConfig.movetext_strips`/
  `movetext_strips_max`, `_strip_candidates`, `_line_carries_notation`, `STRIPS_ENGINE`;
  `_looks_like_movetext` sem os números e pontos no denominador), `tests/unit/ingest/
  test_movetext_strips.py`.
- **Briefing.** Numa região que **não** é movetext mas carrega notação, cada corrida de linhas
  consecutivas com ≥ 2 lances vira uma faixa lida com o perfil `MOVETEXT` (PSM 7 numa linha,
  PSM 6 numa banda; ≤ 8 bandas por região), e as faixas entram na fusão como **um** candidato
  secundário sob nome próprio (`tesseract_strips`) — nunca âncora (§4).
- **Portão.** `bench_sol --strata native,scan_clean_300`, por `genre`: `mixed` sem regressão;
  sabotagem `{"movetext_strips": false}`.
- **Saída.** §B2.

### B3 — NAGs na via de importação (alavanca 16; análise §5.6)

- **Arquivos.** Suíte: `notation/nag_table.py` (`nags_from_suffix`; apelidos `⇄`, `△`, `⊕`,
  `◻`), `ingest/pdf/games.py` (`_move_nodes` preenche `MoveNode.nags` de `RepairedMove.suffix`,
  lado pelo `fen_before`), `benchmarks/notation_integrity.py --what nags [--sabotar nags]`,
  `tests/unit/ingest/test_games.py`.
- **Portão.** `notation_integrity --what nags` nas páginas pinadas do DEM e do Aagaard: nós com
  NAG > 0 (medido 6 em 9 partidas: `$1×2 $2×2 $3×1 $6×1`).
- **Sabotagem.** `--sabotar nags` apaga os símbolos do texto de onde as partidas nascem → 0.
- **Saída.** §B3. O texto do IR fica como impresso (`²` não é reescrito); o NAG vai estrutural.

### B5 — O escore da fusão (alavanca 7; análise §4.3)

- **Arquivos.** Suíte: `ingest/pdf/ocr_service.py` (`OcrServiceConfig.fusion_rescue`/
  `fusion_rescue_moves`, `_rescue_abstained`; `PageRecognition.decision` = REVIEW quando alguma
  região emitida está em revisão), `ocr/fusion.py` (docs).
- **Briefing.** Âncora abstida + candidato **independente** aceito/revisão concordando em ≥ 2
  lances com o fundido → o fundido é re-pontuado pelo árbitro e decidido de novo, **nunca acima
  de REVIEW** (SOL-2), nunca por cima dos pisos de evidência.
- **Portão.** `bench_sol --strata native`: abstidos 62 → menor; `sol_gate` 0 silenciosas e 0/9
  controles; sabotagem `{"fusion_rescue": false}`.
- **Saída.** §B5 (o que a régua mede: um abstido conta CER 0; um rescue com texto certo mas na
  ordem de leitura do PSM 3 conta CER alto — o número é dito com essa ressalva).

### B6 — Escala comum na fusão (alavanca 20; análise §4.6)

- **Arquivos.** Suíte: `ocr/fusion.py` (`FusionConfig.calibrated`, `fuse_candidates(calibrators=)`),
  `ingest/pdf/ocr_service.py` (`_calibrators`: `ArbiterConfig.calibration_for(engine, facet).apply`).
- **Briefing.** As confianças de palavra que a fusão compara passam pelas tabelas calibradas do
  SOL-4 (Tesseract e RapidOCR; o leitor de glifos e o modelo de figurinas ficam na escala crua,
  que é a dos seus limiares). Os três limiares da `FusionConfig` **não** foram recalibrados —
  o efeito medido no corpus decide se ficam (§B6).
- **Portão.** `bench_sol --strata native,scan_degraded_150,fax_dither`; sabotagem
  `{"fusion": {"calibrated": false}}`.
- **Saída.** §B6.

### B8 — O verso real (T7; análise §4.7)

- **Arquivos.** Suíte: `ocr/page.py` (`PageTask.verso_sources`), `ingest/pdf/ocr_service.py`
  (`use_verso`, `verso_min_correlation`, `verso_self_mirror`, `_neighbour_renders`, `_verso_for`),
  `ocr/portfolio.py` (variante `bleed_verso` **ao lado** de `bleed_sauvola`, só ela recebe o
  verso; +1 no teto quando há verso), `tests/unit/ocr/test_verso.py`.
- **Briefing.** Página com `bleed_share` acima do piso: as páginas vizinhas do PDF (e o espelho
  da própria) registradas por `register_verso`; a de melhor correlação acima de 0,08 (piso
  medido: verso certo 0,13, página errada 0,03, ruído 0,001) vira a variante `bleed_verso`. Não
  substitui a heurística: medido, cada uma ganha em páginas diferentes (§4).
- **Portão.** `bench_sol --strata shadow_curl_bleed`; sabotagem `{"use_verso": false}`.
- **Resultado: desligado por medição.** No estrato o `bleed_verso` fez CER 0,0387 → 0,0399 e
  inventados 8 → 10 (dentro do IC, na direção errada): a página do corpus é espelhada **e
  depois** curvada, e o registro global não segue a curvatura. `OcrServiceConfig.use_verso=False`
  guarda os números; o mecanismo fica testado (`test_verso`, 7) à espera de um livro com verso
  real (§4).
- **Saída.** §B8.

### B9 — Paralelo e cancelamento dentro da página (T8; análise §4.8)

- **Arquivos.** Suíte: `ocr/cancel.py` (novo: `OcrCanceled(BaseException)`, `cancellable`,
  `check_cancel` — `ContextVar`), `ocr/engines/tesseract.py` (`Popen` com sondagem do gancho e
  `kill`; `OMP_THREAD_LIMIT=1` no filho; `_forced_profile` por thread), `ingest/pdf/ocr_service.py`
  (`OcrServiceConfig.workers=4`, `_run_readings` com `copy_context`, ordem de submissão),
  `ingest/pdf/importer.py` (`cancellable(should_cancel)` em volta da importação; `OcrCanceled` →
  `ImportCanceled` com o parcial), `tests/unit/ocr/test_cancel.py`.
- **Portão.** `s/MP` `workers=4` × `workers=1` nos estratos de scan; o `ocr_trace` igual nos
  dois (a lista de candidatos guarda a ordem de submissão); teste de que o filho é morto em
  < 5 s quando o gancho diz parar.
- **Sabotagem.** `{"workers": 1}` (o serial); teste do importador com provedor que levanta
  `OcrCanceled` na 2.ª página → `ImportCanceled` com 1 página no parcial.
- **Saída.** §B9.

### C2 — Ler a página com progresso, cancelamento e o gravar trancado (alavanca 10; análise §6.3)

- **Arquivos.** Tronco: `service.py` (`recognize_page(progress=, should_cancel=)`,
  `RecognitionCanceled(partial)`), `qt/trabalho.py` (`Tarefa.cancelar`/`should_cancel`),
  `qt/leitura.py` (novo: `Ocupacao`, `Aquecimento`, as frases), `qt/janela.py` (`_rodar` no
  registro com `total=` e `cancel=`; `_falhou` com os ramos cancelada/sem modelo;
  `painel.trancar_gravacao`; aquecimento ao abrir o livro), `qt/painel_de_resultado.py`
  (`trancar_gravacao`, `mostrar_vazio_sem_modelo`), `ui/busy.py` (`_rodar` sai de
  `FORA_DO_REGISTRO`), `tests/test_qt_leitura.py`, `tests/test_service.py`. Suíte:
  `ui/audit/percurso.py` (`--fluxo casa --frio` / `--cancelar`, sabotagens `sem_aquecimento`,
  `sem_cancelamento`).
- **Portão.** `caissa.ui.audit.progresso` sem defeito bloqueante com `_rodar` registrado;
  `percurso --fluxo casa --cancelar` PASSOU e `--sabotar sem_cancelamento` REPROVOU;
  `--frio` (processo novo) abaixo de **1,5 s** até o primeiro diagrama — medido 0,58–0,64 s com
  o aquecimento, 1,98–2,17 s sem (`--sabotar sem_aquecimento` REPROVOU; o teto de 8 s que este
  passo propunha não reprovaria a sabotagem — §4); `bloqueio` remedido 3/3 PASSOU com o
  aquecimento adiado para 3 s de ócio (§4).
- **Saída.** §C2.

### C3 — Segunda opinião de outra família (alavanca 18; análise §3.5)

- **Arquivos.** Tronco: `qt/painel_de_resultado.py` (`segunda_opiniao`, botão que nasce escondido
  e aparece com leitor configurado; `DIVERGENTE` nas casas em disputa; `Tab` as percorre),
  `qt/tabuleiro_editavel.py` (`definir_casas_disputadas`), `ui/comandos.py`/`ui/menu.py`
  (`segunda_opiniao`), `ui/strings.py`. Suíte: `benchmarks/second_opinion_gate.py` (novo).
- **Portão.** Nos 11 barrados do conjunto de campo (`f4_grade/failures.json`): fração das casas
  erradas cobertas pela disputa ≥ 0,75 — medido **23/27 = 85,2 %**, mediana 2 casas em disputa.
- **Sabotagem.** `--sabotar copia` (o segundo leitor devolve a leitura do primeiro) → 0/27.
- **Saída.** §C3.

### C8 — Trilho que aprende, dúvidas navegáveis, teclado no tabuleiro (alavanca 19; análise §6.6)

- **Arquivos.** Suíte: `ui/trilho.py` (`hesitantes_por_pagina`, `estados(document=,
  diagram_decisions=)`, `proxima_duvidosa`/`anterior_duvidosa`), `ui/views/declarados.py` (novo:
  as tabelas `COMANDOS_DA_ROTULAGEM`/`COMANDOS_DA_REVISAO_DE_TEXTO`), `ui/views/rotulagem.py` e
  `revisao_de_texto.py` (sem os `QShortcut` ambíguos), `ui/audit/percurso.py` (`--fluxo casa
  --teclado`, sabotagem `sem_teclado`; o fluxo `livro` afirma `trilho.aprendeu`). Tronco:
  `ui/teclado_do_tabuleiro.py` (novo, a regra), `qt/tabuleiro_editavel.py` (`StrongFocus`,
  `keyPressEvent`, `definir_duvidosas`), `qt/trilho.py` + `ui/trilho.py` (próxima/anterior),
  `qt/importador_de_livro.py` (`atualizar_trilho`, decisões de diagrama e hesitantes na conta),
  `qt/abas_da_suite.py` (novo: donos e roteamento por aba à frente), `ui/comandos.py`,
  `ui/menu.py`, `ui/atalhos.py` (`Ctrl+Page Up/Down`), `qt/janela.py`.
- **Portão.** `percurso --fluxo casa --teclado` ≤ 3 teclas por casa (`Tab` + letra) — medido
  **2**; `--sabotar sem_teclado` REPROVOU (9); `audit.comandos` 0 soltos (424 medidos);
  `percurso --fluxo livro` afirma `trilho.aprendeu` **quando a página tem diagrama hesitante**
  (no Aagaard 31–38 são 0: a dúvida é de texto — a regra fica pelo `test_trilho` e pelo
  `PonteTests`, §4); testes `TecladoTests`.
- **Saída.** §C8.

### C9 — As abas da suíte pela pele (U6; análise §6.7)

- **Arquivos.** Suíte: `ui/theme/pele.py` (novo: `PAPEIS`, `PARES`, `cor`, `vestir_paginador`),
  `ui/views/{rotulagem,revisao_de_texto,exportacao}.py`, `ui/widgets/cartao_da_linha.py`,
  `ui/audit/contraste.py` (`pares_pintados_da_suite`), `tests/unit/ui/test_pele_da_suite.py`.
- **Portão.** `caissa.ui.audit.contraste` PASSOU com os 8 pares da suíte medidos nas duas
  peles (308 pares, 228 sob portão); `--sabotar` REPROVOU.
- **Saída.** §C9.

### C10 — Coordenadas impressas e o ponto de vista das pretas (D7; análise §3.8)

- **Arquivos.** Suíte: `vision/detect/orientation.py` (`rotate_placement`), `vector_detect.py`
  (gira o `placement` quando `white_at_bottom=False`; as coordenadas lidas em volta das
  **células** em espaço de página — a caixa antiga estava meia casa fora e o leitor de rótulos
  nunca respondia), `ingest/pdf/finders.py` (`point_of_view_from_labels`, `rotate_signal`;
  a via raster gira a FEN, nunca a imagem), `benchmarks/coordinate_survey.py` (novo),
  `tests/unit/detect/test_point_of_view.py`. Tronco: `orientation.py` (`BoardCoordinates.
  files_left_to_right`; `OrientationVerdict.black_point_of_view`; `resolve(turn=)`),
  `inference.py` (`predict_with_orientation(coordinates=)`, `turn` = a mesma matriz vista do
  outro lado), `pdf_text.py` (`board_coordinates_for`, `DiagramContext.coordinates`),
  `service.py` (`RecognizedDiagram.black_point_of_view`), `qt/painel_de_resultado.py`
  (tabuleiro `virado` para bater com o recorte).
- **Portão.** `coordinate_survey.py` (população no acervo); testes com fixture do lado das
  pretas (`coordinates="black"`) → placement canônico; sabotagem = rótulos espelhados
  (`coordinates=True`) → placement como impresso.
- **Saída.** §C10.

### Fase 3 e humano (inalterados)

- **Fase 3 — modelo e ciclo fechado:** C4 (mhsp + RandomStroke com ablação, 13), C5 (calibrador
  de cor + perfil por livro, D6/X3), C6 (fechar o ciclo, X6), C11 (restrições do decodificador,
  D8), A11 (sidecar de proveniência, X4), B10 (cifra com escopo, `figurine_set`, G6/G7).
- **Humano:** 0b (≥ 20 errados), crítico visual C3, decisões do §10 da análise.

## 4. Mutações

| data | passo | mutação | por quê | quem |
|---|---|---|---|---|
| 2026-09-20 | A1 | **portão executado (0,9913 / 1,0000); harness sem troca de atributo** | O pacote virou `RecallOptions` (parâmetro com padrão `DEFAULT_RECALL`) em `detect_boards`/`detect_diagrams`; o `recall_pack(variante)` dos benchmarks passa a variante por `chess_diagram_ocr.config.RECALL_EM_VIGOR` (um `ContextVar`, por thread, com `reset` do token) porque `field_eval` não tem `recall=` — o crítico (Codex, ciclo 1) reprovou a primeira versão, que ainda trocava `bd._extract_candidate_quads`/`hybrid.detect_diagrams` no módulo | construtor + crítico |
| 2026-09-20 | B4 | **sabotagem reescrita**: de `langs=()` para `FusionConfig.passo_b4=False` | Medido: a regra "letra de peça do idioma" é inócua no corpus (inv 18 × 19; lances/CER idênticos) — `langs=()` não reprova o portão (anti-padrão 2). O interruptor desliga os quatro mecanismos do passo (travessão como apoio, `([` e prefixo-sufixo no `_figurine_cut`, concordância entre secundários, guarda de notação longa) e o idioma no `is_move_token`; `SOL_CONFIG='{"fusion": {"passo_b4": false}}'` no `bench_sol` — números em `OCR_UI_REPORT_C2.md` §0.2 | construtor + crítico |
| 2026-09-20 | B7 | **portão reescrito**: recall de `=` não é mensurável — a verdade rotulada (SFC4 `calib`/`dev`/`blind` e os outros dois documentos) não tem um único `=` | O portão fica "`:` e `;` verdade × hipótese > 0 (medido: 10/10 e 1/1) + 204/204 figurinas + ≥ 280 lances", e o `=` fica fixado por teste sobre o tronco real (`test_glyph_postchain`: com `empilhados` um `=` desenhado vira uma caixa; sem, nenhuma toca o `=`). Fechar de verdade exige rotular uma página com promoções (humano — vai para a lista do 0b) | construtor + crítico |
| 2026-09-20 | A3 | **inserido na integração**: `export_book(document=)` recusa documento sem as imagens em disco | O import da janela corria sem `asset_dir` → `Resource.path=None` → o EPUB perderia as imagens em silêncio (crítico Codex). Agora `views/importacao.py` extrai para uma pasta do processo e `export_book` reimporta (com aviso no log) quando falta arquivo; `documento_para` que falha é dito no rodapé | construtor + crítico |
| 2026-09-20 | C7 | **achado do portão `bloqueio`**: as abas da suíte abrindo o livro na thread da janela custavam 209 ms (SHA-256 do PDF inteiro + render) | A Rotulagem só seleciona o documento quando é mostrada (`showEvent`); a Revisão de texto recebe `page_count` da janela em vez de reabrir o PDF. `bloqueio` de 209 ms para 8–12 ms (`OCR_UI_REPORT_C2.md` §0.2) | construtor |
| 2026-09-20 | fase 2 | **rodada de benchmark descartada** | Os A/B da fase corriam em paralelo com os testes das duas árvores; o `s/MP` saiu 12,3 em `scan_degraded_150` (7,3 a sós). Refeita em sequência, sem outro trabalho de CPU; os JSON `f2_*` em `benchmarks/reports/sol/` são os da rodada limpa | construtor |
| 2026-09-20 | B2 | **a faixa vira candidato secundário sob nome próprio** (`tesseract_strips`, `secondary=True`) | A primeira versão entrava como `engine="tesseract"`, `secondary=False`, e a arbitragem a escolhia como **âncora** da região com um subconjunto das linhas: `twocol:d:12` CER 0,0016 → 0,68, Euwe `82:352` → 0,91. Com nome próprio e secundária, só apoia a fusão | construtor |
| 2026-09-20 | B1 | **modo fatia por região** (`PageRecognizer._slice`) | No modo fatia os candidatos da arbitragem partilhada eram de **página inteira** e ancoravam cada região com a página toda (Dvoretsky CER 0 → 0,76). Cada região recebe os candidatos fatiados pela sua caixa. `scan_reread=False` fica por medição (0,0111/42,5 s × 0,0206/66,3 s) | construtor |
| 2026-09-20 | B1 | **duas guardas**: `max_columns=2` e `min_band_chars=16` | Tabela de três faixas (`table:2` CER → 0,47) e lista de lances brancas \| pretas (`18:179:252` → 0,62) têm calha limpa e eram partidas como colunas de prosa. Três faixas = tabela; faixa com mediana de linha < 16 caracteres = lista de lances. `table` e `single` voltam ao antes ao décimo de milésimo | construtor |
| 2026-09-20 | B5 | **`PageRecognition.decision` propaga REVIEW** | O `sol_gate` contava «silenciosa» toda página multi-região cuja âncora aceitava mas uma região emitida estava em revisão (4 páginas); agora a decisão da página é REVIEW quando qualquer região emitida está em revisão — 0 silenciosas | construtor |
| 2026-09-21 | B8 | **`use_verso=False` por padrão** | Medido no `shadow_curl_bleed`: CER 0,0387 → 0,0399, inventados 8 → 10 com a variante ligada (registro global contra página curvada). O mecanismo fica com testes e interruptor; a decisão pede um livro com verso real | construtor |
| 2026-09-21 | C2 | **aquecimento adiado para 3 s de ócio** (`leitura.ESPERA_PARA_AQUECER_MS`, reiniciado a cada virada de página, nunca com tarefa em curso) | A carga do modelo ao abrir o livro é C que segura o GIL: `bloqueio` VIOLA («abrir PDF» 28–45 ms, primeira virada 57–84 ms). Adiado, 3/3 PASSOU («abrir PDF» pior 14,8/11,8/6,6 ms); o primeiro «Ler» continua a 0,6 s porque o aquecimento acaba antes de a pessoa chegar à página. O `closeEvent` espera o aquecimento (uma `QThread` destruída a correr matava o processo da auditoria `comandos`) | construtor |
| 2026-09-21 | C2 | **teto do `--frio` de 8 s para 1,5 s** (`percurso.TETO_FRIO_S`) | A sabotagem `sem_aquecimento` mede 1,98–2,17 s — não cruzaria 8 s (anti-padrão 2). O teto ficou entre os dois números medidos (0,58–0,64 s com aquecimento) | construtor |
| 2026-09-21 | C8 | **`Tab` percorre as casas na ordem da dúvida** (`teclado_do_tabuleiro.proxima_duvidosa` respeita a ordem da lista; o painel ordena por margem) | O portão `--teclado` reprovou a primeira versão: em ordem de tabuleiro eram 8 `Tab` até e2. Com a casa de menor confiança primeiro, 1 `Tab` + letra = 2 teclas | construtor |
| 2026-09-21 | C8 | **o tabuleiro em foco toma para si `←`/`→`/`Del`** (`DonoDeAcoes` em `TabuleiroEditavel`; `teclado_do_tabuleiro.ACOES_DAS_SETAS`, `ACAO_DE_APAGAR`) | As setas e o `Delete` são atalhos globais e a guarda de atalhos é um filtro na aplicação: o `keyPressEvent` do passo nunca as recebia na janela de verdade (o teste do widget sozinho passava; a suíte inteira do tronco reprovou depois de qualquer teste que ligasse a guarda). É a regra da S-244, a mesma que dá `←` ao campo de texto em foco; teste com a guarda ligada + sabotagem | construtor |
| 2026-09-21 | C8 | **`trilho.aprendeu` afirmado só com hesitante na página** | No Aagaard 31–38 os 13 diagramas leem com folga; a dúvida do trilho é de texto e a correção de um diagrama não a muda — afirmar `aprendeu` ali seria afirmar o que a página não tem. O fluxo `livro` diz em nota; a regra fica no `test_trilho` (hesitante → decidido) e no `PonteTests` | construtor |
| 2026-09-21 | C9 | **`regiao_selecionada` → `TRACEJADO`** | O papel `ALVO` da pele media 1,65:1 sobre a página na auditoria de contraste (o par da suíte reprovava); o tracejado é o traço de seleção que a pele já tem sob portão | construtor |
| 2026-09-21 | C9 | **palavras fracas do cartão na letra, não no fundo** (`cartao_palavra_conferir` = `ATENCAO`, `cartao_palavra_revisar` = `PROBLEMA_TEXTO`) | A primeira versão mapeava os fundos âmbar/vermelho do cartão para `REALCE_NOTA`/`REALCE_DESTAQUE`, que na tabela de significado do tronco são o canal de **quem escreve** (`REALCE_NOTA` é verde): a suíte inteira acusou `#b9ffc5` atrás de uma palavra duvidosa. A regra do editor do tronco (`ui/texto_cores.py`) é confiança na letra; `contraste` remedido 308/228 PASSOU com os 8 pares | construtor |
| 2026-09-21 | B3/C3 | **`CAISSA_FIGURINE_TESSDATA` só no `bench_sol`** | Com a variável no ambiente o `config` do tronco recusa o caminho e o classificador de diagramas não carrega — o portão do B3 (partidas sob diagramas) contava 0 partidas por isso, não pelos NAGs. Portões que precisam de diagramas lidos correm sem ela | construtor |
