# OCR/UI — roadmap do ciclo 2

> **Data:** 2026-09-20 · **Fonte:** `docs/OCR_UI_ANALISE_C2.md` (aprovada pelos críticos; §0 =
> as 20 alavancas, §8 = a ordem). Este documento detalha a **fase 1** (fiação e perdas
> silenciosas) com o formato do ciclo 1 — briefing frio, arquivos, portão, sabotagem, "Saída" —
> e lista as fases 2 e 3 por alavanca, a detalhar quando a 1 fechar. Relatório do construtor:
> `docs/quality/OCR_UI_REPORT_C2.md` (uma seção por passo, todo número com o comando ao lado).
> Não substitui `OCR_UI_ROADMAP.md` (ciclo 1), cujas pendências humanas (0b, crítico C3) continuam.
> **Fase 2** (§3) executada em 2026-09-20/21 — relatório `docs/quality/OCR_UI_REPORT_C2_FASE2.md`.
> **Fase 3** (§3b) executada em 2026-09-21 — relatório `docs/quality/OCR_UI_REPORT_C2_FASE3.md`.
> **Fase 4** (§3c) — o que a análise nomeia fora das 20 alavancas (§3.10, §4.9, §6.9, §10.6) e o
> que os relatórios e os críticos deixaram como dívida nomeada; executada em 2026-09-21 — relatório
> `docs/quality/OCR_UI_REPORT_C2_FASE4.md`.
> **Fase 5** (§3d) — definida em 2026-09-23 a partir da massa de erro do `sol.json` da fase 4
> (a tabela lida por coluna, o texto perdido e aceito) e das dívidas medidas e sem dono; executada
> no mesmo dia — relatório `docs/quality/OCR_UI_REPORT_C2_FASE5.md` (o portão de 150 DPI do Sol
> verde pela primeira vez; aceitos errados 30 → 7).

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
  PyQt6 no topo); desde a fase 5 (A15) o `tests\unit\ui\test_arquitetura.py` roda **na mesma
  corrida** (a afirmação «nenhum binding de Qt em `sys.modules`» é feita num processo novo por
  arnês); testes do tronco, **sem `--deselect`** desde a fase 5 (os relatórios de campo correntes
  remedidos no commit); `benchmarks\sol_gate.py --report-only docs\quality\sol\sol.json`
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
Tronco: commits **2077410 → b20cd6f**; suíte: **b156222 → c13baca** (fase, revisão do construtor,
crítica). Crítico Codex: ciclo 1 REPROVADO (5 bloqueantes), ciclo 2 **APROVADO** — vereditos em
`docs/quality/OCR_UI_ANALISE_C2_CRITICAS.md`, «Fase 2».

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

## 3b. Fase 3 — modelo e ciclo fechado (executada em 2026-09-21)

Mesmo formato: **arquivos** · **briefing** · **portão** · **sabotagem** · **saída**. O relatório
é `docs/quality/OCR_UI_REPORT_C2_FASE3.md` (uma seção por passo, número com comando ao lado).
Construída por uma sessão só, com o treino da ablação (C4) correndo em segundo plano na GPU
enquanto os outros passos eram medidos — o `s/MP` e o `s/diagrama` desta fase carregam essa
contenção e são ditos com ela. Ordem executada: C4 (lançado primeiro, é o mais longo) → B10 →
C11 → C5 → C6 → A11. Os passos que trocam o `.pt` de produção ou o perfil de um livro
**não** o fazem sozinhos: são as decisões 2 e 4 do §10 da análise (§3b.7).

### C4 — `mhsp` + `RandomStroke`, com ablação (alavanca 13; análise §3.4)

- **Arquivos.** Tronco: `augment.py` (`RandomStroke`, `stroke()`, `AugmentConfig.stroke`/
  `stroke_px`/`stroke_margin_px`, letra `e`, `from_letters`, `version_of_checkpoint`),
  `training.py` (piso do cache por processo = `BOARDS_PER_CHUNK`), `cli/train.py` (`--augment
  mhspe`), `ui/pedido_de_treino.py` + `qt/dialogos.py` (a janela retreina no regime do
  checkpoint de produção, `TrainingRequest.augment`), `tests/test_augment.py` (+8),
  `tests/test_training.py` (+1), `tests/test_configuracoes.py` (+1). Suíte:
  `benchmarks/c4_ablation.py` (novo: treina cada variante do zero, mesma semente e partição,
  `assign_splits=False`; histórico por época em `benchmarks/reports/c4_ablation/`),
  `benchmarks/lab_gate.py` (`--rules`, colunas `helped`/`hurt`).
- **Briefing.** `RandomStroke` engrossa ou afina a tinta por morfologia em `max_pool2d` (sem
  `cv2` no `DataLoader`), só no interior da casa (anel de 3 px intacto: grade e hachura
  vizinha não são glifo). **1 px, medido**: com 2 px a torre branca em casa hachurada do
  Koblenz vira um bloco preto (fração clara dentro do glifo 0,84 → 0,34, mínimo 0,04) — a
  proposta dizia «1–2 px» e o rótulo não sobrevive a 2. A ablação treina `aug0` × `mhsp` ×
  `mhspe` × `e` do zero, 16 épocas, semente 42 (e 43/44 quando o tempo deu), sem tocar
  `splits.csv`; o `.pt` de produção fica onde está.
- **Portão.** `lab_gate --candidate … --runs 3 --unconstrained` (3× verde, sem regressão de
  acurácia por casa nem de ilegais), `field_exact --model …` com `exported_wrong` ao lado, e
  `f4_field_failures --model …` para as trocas X↔x. O que passou e o que não passou está em
  §C4 do relatório; a troca do `.pt` é decisão da pessoa (§10.2). **Resultado (sementes 42,
  43, 44): nenhuma variante domina** — o `aug0` varia mais entre sementes (553–556 no teste,
  1–4 exportados-e-errados no campo) do que qualquer variante difere dele, e o `RandomStroke`
  fica um pouco abaixo em todas as médias; nada a trocar.
- **Sabotagem.** `--augment i` sozinho (inversão **sem** troca de rótulo) tem de piorar a cor
  — treinado na mesma grade. **Medido: não piorou** — a letra `i` inverte em 3 %, e a 3 % o
  `c4_i_s42` é indistinguível do `aug0` (556 = 556 no teste; 4 casas de cor contra 5 no campo);
  `i50` (`SABOTAGE_VARIANTS`, inversão em metade dos lotes) também: 553 no teste, 7 casas de cor
  contra 5–8. Inverter sem trocar o rótulo não confunde a cor. Vermelho no relatório; a próxima
  sabotagem é ruído de rótulo `X↔x` em 10 % das casas.
- **Saída.** §C4. **Achado que valeu a fase:** o cache do dataset por processo dividia 128 por
  5 = 25 tabuleiros para uma janela de 64 do amostrador: cada casa reabria o PNG e a época
  custava **10,1 min** (na GPU!); com o piso na janela, **3,2 min** (`loader_probe`, 400 lotes:
  111 s → 35 s). O treino da janela herda o mesmo piso.

### B10 — Cifra com escopo, `figurine_set`, proveniência do `PieceGlyph` (G6/G7; análise §5.7)

- **Arquivos.** Suíte: `ocr/notation/book_cipher.py` (formato 2: evidência por peça e fonte,
  **maioria** em vez da primeira observação, estilo por classe de tamanho da linha —
  `size_class`/`body_size_of` —, janela de páginas, exemplos com confiança; lê o formato 1),
  `ingest/pdf/ocr_service.py` (`cipher_style`/`cipher_window`/`cipher_majority`; o corpo da
  página; `_observe_glyph_swaps` com estilo e confiança; `to_page_text` com um span por
  palavra com figurina e a origem em `TextSpan.figurine_origin` — `glyph`, `tesseract_figurine`
  ou `cifra`; o `engine` continua o OCR que leu as palavras), `ingest/pdf/importer.py`
  (`PdfImportOptions.ocr_config`; `PieceGlyph` com `figurine_set` e proveniência própria),
  `benchmarks/notation_integrity.py` (`--sabotar cifra_estilo|cifra_janela|cifra_primeira|
  cifra_plana`), `tests/unit/ocr/test_book_cipher.py` (+6), `test_glyph_engine.py` (+1),
  `tests/unit/ingest/test_figurine_provenance.py` (novo, 3).
- **Portão.** `notation_integrity --what contest` nas oito páginas do Gaprindashvili, seis do
  Aagaard e do Nunn, com as tabelas restauradas do mesmo instantâneo antes de cada corrida:
  peça certa **914 → 917** (de 986), 157 → 157 (204), 363 → 363 (472); controles Dvoretsky e
  Boleslávski 0 caracteres alterados.
- **Sabotagem.** `--sabotar cifra_plana` (estilo, janela e maioria desligados) → **914**, o
  antes. Uma a uma: estilo desligado 917, janela desligada 917, maioria desligada 917 — o ganho
  precisa de **estilo ou janela** (cada um basta sozinho); a maioria não moveu nada nestas
  páginas (§B10 do relatório diz isso, e por quê).
- **Saída.** §B10. O `♕` do texto sai `♕` no DOCX/EPUB (antes `♛`), e a revisão distingue a
  figurina lida (0,99) da inferida pela cifra (`Provenance.note`).

### C11 — Restrições do decodificador e o lance seguinte (D8; análise §3.9)

- **Arquivos.** Tronco: `decode.py` (`DecodeRules`/`CLASSIC_RULES`: bispos do mesmo lado em
  casas da mesma cor contam como promovidos na conta de peões ausentes; reis adjacentes),
  `inference.py` (`prediction_with_squares`), `evaluation.py` (`rules=`, `decode_rules` no
  JSON), `lance_seguinte.py` (novo: `conferir`, `apply_next_move`), `pdf_text.py`
  (`DiagramContext.first_moves_text`), `service.py` (`RecognitionOptions.next_move`,
  `RecognizedDiagram.next_move*`, `gate_confidence`), `pdf_to_pgn.py` (o mesmo caminho na
  exportação; `[OCRNextMove]`), `field_eval.py` (gate por `gate_confidence`; contadores
  `next_move_*`), `tests/test_decode.py` (+8), `tests/test_lance_seguinte.py` (novo, 11),
  `tests/test_field_eval.py` (+2). Suíte: `benchmarks/field_exact.py` (`--sabotar
  sem_lance|lance_vizinho`), `tools/f4_field_failures.py` (`--sem-lance`, campos `next_move*`),
  `vision/classify/confidence.py` (`DiagramSignals.next_move_replays`, fora do vetor ajustado).
- **Briefing.** (a) as duas violações novas em `_find_violations`, a dos bispos condicionada
  aos peões. (b) O primeiro lance impresso sob o diagrama é jogado na posição (`text.notacao.
  validar`); se não fecha, as segundas opções das casas hesitantes (margem < 0,9) e a **outra
  cor** de cada peça lida são tentadas (≤ 2 trocas), e a troca **única** que faz a linha fechar
  até o 3.º lance impresso é adotada — uma linha de um lance só confirma, nunca troca. A casa
  trocada fica com a confiança da matriz; o gate julga as outras (`gate_confidence`).
- **Portão.** (a) `lab_gate --runs 3` produção: `--rules classic` 0,9770 (553/566, `helped` 0)
  → C11 **0,9806** (555/566, `helped` 2, `hurt` 0), ilegais 0 nos dois. (b) `field_exact`:
  `next_move_checked` **2** de 114 — o conjunto de campo tem dois diagramas com linha de lances
  sob eles (livros de problemas e de exercícios) — `next_move_repaired` 0; `games_gate`
  inalterado (população 0,04, como a análise previu). A mecânica fica pelos 11 testes.
- **Sabotagem.** `lab_gate --rules classic` (o de antes); `field_exact --sabotar lance_vizinho`
  (cada diagrama recebe a linha do vizinho) — **inerte** no campo pela mesma população de 2;
  no teste, a linha do vizinho não troca nada (`test_the_neighbours_move_repairs_nothing`).
- **Saída.** §C11.

### C5 — Calibrador de cor por livro, dentro do perfil do livro (D6/X3; análise §3.7, §7.3)

- **Arquivos.** Tronco: `cor_por_livro.py` (novo: `medir` — média de cinza dos 40 % centrais
  da casa —, `CalibradorDeCor` com amostras **por peça e cor da casa** (`chave_da_amostra`,
  `"Qe"`/`"Qc"`), `decidir` pelos extremos com margem de 10 níveis, só quando as duas cores se
  separam aparada uma amostra de cada lado, `trocas_de_cor` quando o par `(X, x)` domina a
  casa, `apply_colour` com a guarda
  de legalidade, `calibrador_do_livro` lendo o perfil da suíte quando ela está importável),
  `service.py` (`RecognitionOptions.colour`/`colour_calibrator`; `RecognizedDiagram.colour_*`,
  `external_repairs`), `pdf_to_pgn.py` (`[OCRColour]`), `field_eval.py` (`colour_*`),
  `tests/test_cor_por_livro.py` (novo, 14). Suíte: `ocr/book_profile.py` (novo: `BookProfile`
  — identidade, `ocr_config`, `colour`, `history` — em `models/tessdata/livros/<slug>/
  perfil.json` ao lado de `cipher.json`), `ingest/pdf/importer.py` (o perfil sob as opções
  explícitas), `benchmarks/field_exact.py` (`--sabotar sem_cor|cor_trocada|sem_evidencia`,
  `--perfil`), `tools/f4_field_failures.py` (`--sem-cor`, `--perfil`, campos `colour_*`).
- **Briefing.** Medido nos recortes de campo antes de escrever: no Koblenz as pretas medem
  81–154 e as brancas 148–219, e as cinco casas de cor erradas caem do lado certo; no Burgess
  ≤ 48 × ≥ 137; no Niemeijer e no Stefaniu as cores se sobrepõem — ali o calibrador se
  abstém. As amostras são as dos diagramas **corrigidos** do livro (C6); o tabuleiro não é
  amostra de si (uma peça por lado e por cor de casa nunca chega ao mínimo de 5, e onde chegava
  — os peões — a régua errou: Stefaniu p100 `b2 P→p`, seguro só pela guarda de legalidade).
- **Portão.** `caissa.ocr.closing` no Koblenz, deixando um de fora de cada vez sobre os 22
  diagramas corrigidos fora das páginas de campo: k = 6 e 12 → 0 trocas (as damas não chegam a
  5 por cor de casa); k = 22 → **6 trocas, 6 certas** (casas de cor erradas 22 → 16; exatos 1 →
  2). No campo (`field_exact`, perfil do Koblenz aprovado): exatos **103 → 106** (Koblenz 0/4 →
  3/4, as quatro damas `q→Q` de p30/p50 trocadas), `exported_wrong` 3 → 3, `lab_gate` intacto
  por construção (o calibrador roda no serviço, não em `evaluate_dataset`).
- **Sabotagem.** `--sabotar sem_cor` → 103; `--sabotar cor_trocada` (as amostras brancas e
  pretas do perfil trocadas) → §C5 do relatório.
- **Saída.** §C5. Os três Koblenz exatos continuam **não exportados**: o decodificador também
  reparou outras casas deles (S-132, «reparado nunca exporta», que o calibrador não toca).

### C6 — Fechar o ciclo corrigir → medir → melhorar (X6; análise §7.6)

- **Arquivos.** Suíte: `ocr/closing.py` (novo: `close_cycle`, `collect_text_pairs`,
  `collect_diagram_truths`, `field_pages_of`, `default_blind_guard`; CLI `caissa-fechar-ciclo`
  em `pyproject.toml`), `tests/unit/ocr/test_closing.py` (novo, 5).
- **Briefing.** Um comando por livro: consome as correções de texto (fila de revisão e projeto
  de rotulagem) num **manifesto de calibração** JSONL e as correções de diagramas
  (`labels.csv` do tronco com procedimento humano, decisões da janela) no calibrador de cor;
  retém o que a guarda cega diz e **as páginas do conjunto de campo** (o campo mede, nunca
  alimenta); mede antes/depois (um de fora de cada vez); grava `model_identity`, hash dos
  rótulos, hash do documento e commit; escreve `perfil.proposto.json` e só com `--aprovar` o
  `perfil.json`.
- **Portão.** Koblenz (§C5); o manifesto e o perfil gravados; `git status` limpo (os dois vivem
  em `models/` e `labeling/`, ignorados).
- **Sabotagem.** Decisão numa página cega → retida e contada (`test_a_blind_page_and_a_field_
  page_contribute_nothing`, `test_text_corrections_become_calibration_pairs_minus_the_blind_
  page`); a primeira versão do comando incluiu as duas amostras da p. 50 do Koblenz (página de
  campo) no perfil — o campo teria medido a si mesmo; a regra das páginas de campo nasceu daí.
  E a segunda ainda as incluía: o `labels.csv` grava a página em base 1 e o campo em base 0
  (§4, `_page_index_of_label`) — apareceu ao listar as trocas do um-de-fora casa a casa.
- **Saída.** §C6.

### A11 — Sidecar de proveniência (X4; análise §7.4)

- **Arquivos.** Tronco: `proveniencia.py` (novo: `Cabecalho`, `registro`, `write_sidecar`,
  `read_sidecar`, `verificar`, `ColisaoDeProveniencia`), `pdf_to_pgn.py` (`DiagramPosition.
  bbox_pdf`/`image_hash`/`square_confidences`/`repairs`; `write_gated_pgn(provenance=)` grava
  `<nome>.proveniencia.jsonl` e os dois PGNs apontam com `[ProvenanceFile]`/`[ProvenanceKey]`;
  `ExportReport.provenance_path`), `export_checkpoint.py` (os campos novos no parcial),
  `tests/test_proveniencia.py` (novo, 5). Suíte: `export/provenance.py` (novo: o mesmo sidecar
  ao lado do EPUB/DOCX, a partir do IR — `Diagram.source`, `recognition`, `verified_by_human`,
  `GameScore`), `export/book.py` (`BookExportResult.provenance_path`), `tests/unit/export/
  test_provenance_sidecar.py` (novo, 3).
- **Briefing.** Chave estável `p<página>:d<índice>` — a do `[Diagram]` e do A3 —, nunca a FEN;
  o sidecar é aditivo (quem não o lê não perde nada do PGN); no IR a linha leva também o ULID.
- **Portão.** Um item sintético exportado e relido volta inteiro (retângulo, hash do recorte,
  64 confianças, reparos, decisão humana, modelo, perfil, veredito do gate).
- **Sabotagem.** Dois diagramas com a mesma FEN em páginas diferentes com chave por FEN →
  `ColisaoDeProveniencia`, com as duas páginas na mensagem; a chave normal os mantém dois.
- **Saída.** §A11.

### 3b.7 Humano (inalterado) e decisões que esta fase deixa

- 0b (≥ 20 errados), crítico visual C3, e as decisões do §10 da análise que esta fase põe na
  mesa com número: **§10.2** (trocar o `.pt` de produção pelo vencedor da ablação — §C4 do
  relatório diz qual e com que margem), **§10.4** (o perfil por livro em `models/tessdata/
  livros/<slug>/perfil.json`, ao lado da cifra, que o `--importar-acervo` do bundle já leva),
  **§10.5** (o sidecar ao lado do PGN e do livro, `.proveniencia.jsonl`).

## 3c. Fase 4 — o que nenhum portão media, e a evidência que faltava (executada em 2026-09-21)

As três fases cobriram as 20 alavancas do §0 da análise. O que sobrou está **fora** dessa
tabela e foi dito com endereço: as notas menores (§3.10, §4.9, §5.8), «o que nenhum portão mede
hoje» (§6.9), a decisão §10.6 (EPUBCheck), os «não bloqueantes» que os críticos deixaram para
a fase seguinte (`OCR_UI_ANALISE_C2_CRITICAS.md`, fase 1 ciclo 2, itens 5–8) e o §0.3 do
relatório da fase 3 (a sabotagem inerte do C4, o campo contaminado, os rótulos sem partição).
Esta fase é isso, no mesmo formato: **arquivos** · **briefing** · **portão** · **sabotagem** ·
**saída**. Relatório: `docs/quality/OCR_UI_REPORT_C2_FASE4.md`. Construída por uma sessão só,
com o treino do C16 na GPU em segundo plano (os tempos carregam a contenção e são ditos com ela).
Ordem executada: C16 (lançado primeiro, é o mais longo) → C12 → A12 → B11 → B12 → A13 → C14 → C15.

**O que a fase não toma, e por quê** (para ninguém reabrir sem número novo): desenho vetorial
com assinatura desconhecida → casa vazia e `Diagram.marks` (§3.10): `vector_survey_20260914`
conta **0** `drawing_boards` nos 46 livros — sem população, fica como defeito nomeado; fonte de
diagrama inline apagando a figurina (§5.8): população 0, a própria análise diz «não é passo»;
idioma por página (§4.9): nenhum item bilíngue no corpus — portão impossível; decodificar as
duas orientações (§3.10, 15–20 % de `decode_s`): trocaria decisões de orientação para ganhar
milissegundos; o desenho dos vazios (§6.10) e o alto contraste **como pele nova** são do
crítico visual C3 (humano) — aqui só a detecção e a régua; A2 «com portão de aceitação»
(crítico da fase 1, item 8): o EPUB já diz a dúvida por casa (C1) e no alt text (A9), e
**não desenhar** um diagrama lido abaixo do portão é a decisão §10.1 da pessoa, não do
construtor.

### C12 — A estipulação como evidência (§3.10, §6.9, SPEC §6.4; a hipótese da S-33)

- **Arquivos.** Tronco: `estipulacao.py` (novo: gramática `Estipulacao`, o verificador
  `verificar` — busca exaustiva em python-chess para mate em 1–2, Stockfish `go mate N` quando
  `engine.find_engine` o acha, para 3–4 —, `conferir` com as mesmas candidatas do C11 e
  `apply_stipulation`), `pdf_text.py` (`DiagramContext.stipulation`, o padrão de legenda
  `#2`/`3‡`/`Mate in two`/`Matt in 3 Zügen`/`mate em 2`/`mat en 3`, e o escopo de página
  «Combinations #2»), `service.py` (`RecognitionOptions.stipulation`; `RecognizedDiagram.
  stipulation`, `stipulation_closes`, `stipulation_repairs`, `stipulation_reason`, entram em
  `external_repairs`), `pdf_to_pgn.py` (`[Stipulation]`, `[StipulationCheck]`, a nota do
  reparo), `proveniencia.py`, `field_eval.py` (contadores `stipulation_*`), `qt/painel_de_
  resultado.py` + `ui/strings.py` (a frase no painel), `README.md` (árvore), testes. Suíte:
  `ingest/pdf/captions.py` (a mesma gramática, com teste de paridade contra o tronco),
  `importer.py` (`Diagram.stipulation` = «Mate em 2», `Diagram.solution` com a chave quando
  fecha, aviso quando não fecha), `benchmarks/field_exact.py` (`--sabotar sem_estipulacao`,
  contadores no JSON).
- **Briefing.** Um livro de problemas imprime a exigência ao lado do diagrama, e a exigência é
  **verificável**: «mate em 2» ou fecha na posição lida ou não fecha. Hoje `importer.py` só
  preenche «Brancas jogam» e `Diagram.solution` nunca existe; a S-33 registrou a hipótese
  («uma avaliação bizarra sugere erro de OCR») como não feita. O mecanismo é o do C11 com outro
  predicado: joga-se a **exigência** em vez do lance impresso; se não fecha, tentam-se as
  segundas opções das casas hesitantes e a cor de qualquer peça, e adota-se a troca única que
  faz fechar. Mate em 2 é busca exaustiva barata (ordem de 10³ nós); mate em 3–4 é o motor
  quando existe (`CVOFF_ENGINE_PATH`; nesta máquina o Stockfish do Sigil) e «não verificado
  (sem motor)» quando não. Uma exigência que não fecha **nunca** apaga a leitura: vira estado
  com ação (revisão) e frase.
- **Portão.** No conjunto de campo (`field_exact --runs 3`): (a) toda verdade anotada com
  estipulação lida fecha (`stipulation_truth_closes` = `stipulation_checked`; se uma verdade
  não fecha, ou a gramática leu errado ou a anotação está errada — e o relatório diz qual);
  (b) `stipulation_repaired_wrong` = 0; (c) os exatos não caem. **Sabotagem:** `--sabotar
  sem_estipulacao` (`RecognitionOptions.stipulation=False`) devolve `stipulation_checked` 0 e
  os exatos de antes; `estipulacao_vizinha` dá a cada diagrama a exigência do vizinho — um
  sinal que ainda «fecha» sob isso alimenta-se de coincidência.
- **Saída.** `[Stipulation "#2"]` e `[StipulationCheck "fecha"|"não fecha: …"]` no PGN;
  «Mate em 2 — fecha (1.♕h7#)» / «não fecha nesta leitura» no painel; `Diagram.stipulation` e
  `Diagram.solution` no EPUB/DOCX; os contadores no JSON do campo.

### A12 — EPUBCheck como invariante (§6.9, §10.6)

- **Arquivos.** Suíte: `tests/unit/export/corpus.py` (`epubcheck_jar` procura também
  `tools/epubcheck*/epubcheck.jar` na raiz do repositório e `%LOCALAPPDATA%\Caissa\`),
  `tools/instalar_epubcheck.py` (novo: desempacota um `epubcheck-*.zip` — nesta máquina o que o
  Sigil já baixou em `%TEMP%\sigil-epubcheck-*\epubcheck.zip`, 4.2.6, Java 8 basta — em
  `tools/epubcheck-<versão>/`, ignorado pelo git), `.gitignore`, `ui/audit/percurso.py` (o
  fluxo `livro` roda o EPUBCheck sobre o EPUB exportado quando o jar existe e conta os erros),
  `tests/unit/export/test_epubcheck.py` (novo).
- **Briefing.** A SPEC §11.3 exige «0 erros» e o `ROADMAP.md` publica «EPUBCheck 0 erros», mas
  o teste é **pulado** quando o jar não está na máquina — e não estava. Um portão declarado que
  não roda em invariante nenhuma é um portão que passa cego. O jar fica fixado por caminho do
  repositório (ou `CAISSA_EPUBCHECK`), o `percurso --fluxo livro` passa a validar o EPUB de
  verdade e a suíte deixa de pular.
- **Portão.** `pytest tests/unit/export -k epubcheck` **não pulado**, 0 erros no corpus; `percurso
  --fluxo livro` com `epubcheck_erros = 0` no JSON. **Sabotagem:** um pacote com o `mimetype`
  errado / o `nav` fora do manifesto (`test_epubcheck`: `run_epubcheck` conta ≥ 1 erro e a
  função que o portão usa reprova); `--sabotar sem_epubcheck` no `percurso` → o JSON diz
  «EPUBCheck não rodou» e o portão reprova.
- **Saída.** O «0 erros» da SPEC medido em toda invariante nesta máquina.

### B11 — O instrumento mede o que o produto faz: `_xheight_px` e a abstenção que não é CER 0 (§4.9)

- **Arquivos.** Suíte: `ocr/portfolio.py` (`_xheight_px(gray, dpi)`: teto físico de componente
  — 0,25 pol — em vez de 5 % da altura da imagem), `benchmarks/bench_sol.py` + `ocr/metrics.py`
  (`cer_all`: CER sobre **todos** os itens rotulados, com a abstenção valendo o texto do
  melhor candidato — ao lado do CER dos aceitos, nunca no lugar), `ocr/gates.py`/`sol_gate.py`
  (a coluna publicada), `docs/quality/sol/sol.json` + `sol.md` **republicados** com o
  instrumento corrigido (estavam em `69583fd`, 2026-09-13; o `baseline.json` é o sistema de
  referência Tesseract-só e não muda), testes.
- **Briefing.** `_xheight_px` mantém componentes de altura ≤ 5 % da imagem: numa folha inteira
  são 165 px (tudo que é letra entra); num item sintético de 382 px são 19 px, as letras saem e
  ficam pingos e vírgulas — a altura-x lê 5 px, a página é tratada como degradada e o benchmark
  roda RapidOCR + upscale onde o produto, com páginas inteiras, não roda. O benchmark media o
  que o produto não faz. Depois: o teto é físico (uma letra nunca passa de 0,25 pol), igual
  nos dois casos. E «abstenção = CER 0» esconde o T2: `cer_all` diz quanto texto a página
  perde de fato.
- **Portão.** `detect_signals` sobre o mesmo parágrafo solto e colado numa folha A4 dá a
  mesma altura-x (± 1 px; hoje 5 × 20); `bench_sol` remedido; `sol_gate --report-only` 0
  silenciosas, 0/9 controles no `sol.json` novo. **Sabotagem:** `SOL_CONFIG='{"portfolio":
  {"xheight_relative": true}}'` devolve o teto relativo e o número de antes.
- **Saída.** `sol.md` com `cer_all` por estrato; o baseline diz com que instrumento foi medido.

### B12 — O DPI real chega ao Tesseract; as ligaduras dobram na fronteira (§4.9)

- **Arquivos.** Suíte: `ocr/arbiter.py` (`RegionTask.dpi`; o árbitro entra em
  `engine.with_dpi` quando o motor o tem), `ocr/engines/tesseract.py` (`with_dpi`: `--dpi` = o
  DPI da variante que o portfólio entregou, não 300 fixo), `ocr/page.py` +
  `ingest/pdf/ocr_service.py` (`variant_dpi`, um interruptor só; `_read_on_variant` passa
  `variant.dpi`), `ocr/engines/normalize.py` (novo: `fold_ligatures` — `ﬁ ﬂ ﬀ ﬃ ﬄ ﬅ ﬆ` →
  letras; **não** NFKC, que trocaria `½` por `1⁄2` e `²` por `2`), aplicado na saída de todo
  motor em `engines/base.py`, testes.
- **Briefing.** O upscale entrega 450 DPI e o Tesseract é informado de 300: a estimativa de
  tamanho de fonte dele erra por 1,5 e a segmentação de linhas paga. A ligadura `ﬁ` do
  Tesseract entra no IR como U+FB01: o métrico normaliza e não vê, o EPUB e a busca veem.
- **Portão.** Teste de unidade da fronteira (`ﬁ` nunca sai de um motor); `bench_sol` nos
  estratos com upscale (`scan_degraded_150`) CER ≤ o de antes (dentro do IC) e sem regressão
  nos outros. **Sabotagem:** `SOL_CONFIG='{"variant_dpi": false}'` fixa o antes.
- **Saída.** O IR sem ligaduras; o Tesseract sabendo a resolução que recebe.

### A13 — Recursos por importação; um rodapé só; `paralelo` booleano (críticos da fase 1, itens 5–7)

- **Arquivos.** Suíte: `ui/views/importacao.py` (`_pasta_de_recursos()` → uma pasta **por
  importação**, `<stem>-<n>`, apagada quando a importação seguinte do mesmo livro a substitui e
  ninguém exporta dela), `ui/audit/paralelo.py` (`troca_de_livro` com os booleanos julgados
  por nome, não `all()` sobre strings), teste. Tronco: `qt/importador_de_livro.py`
  (`_concluiu` cala quando o cancelamento foi por troca de livro — a ponte já diz a frase).
- **Briefing.** Uma pasta por processo para todas as importações: `diagrama-p31-0001.png`
  colide entre dois livros com as mesmas páginas, e uma exportação em curso lê arquivos que a
  importação seguinte sobrescreve. E dois rodapés contraditórios em 1 s ao trocar de livro.
- **Portão.** `paralelo --pdf Kemeri --pagina 80 --outro-livro X`: os recursos dos dois livros
  em pastas distintas e a exportação do primeiro relê os dele; rodapé com **uma** frase.
  **Sabotagem:** `--sabotar pasta_partilhada` → colisão acusada; `_relatorio` com um booleano
  falso → reprova (teste).
- **Saída.** O que o crítico pediu, medido.

### C14 — O tabuleiro fala ao leitor de tela; os portões a 150 %/200 %; alto contraste (§6.9, Carta §3.2)

- **Arquivos.** Tronco: `qt/tabuleiro_editavel.py` (`_anunciar`: `accessibleName` = «Tabuleiro,
  casa e2 selecionada: peão branco» a cada seleção — o PyQt6 não expõe `QAccessible`, e não
  precisa: o próprio `QWidget.setAccessibleName` emite o `NameChanged` de acessibilidade; o
  rodapé continua), `ui/strings.py` (`nome_acessivel_do_tabuleiro`), `qt/plataforma.py`
  (`alto_contraste_ativo()`: `SPI_GETHIGHCONTRAST` por ctypes no Windows, `CVOFF_ALTO_CONTRASTE`
  força para o arnês, `False` fora), `qt/tema.py` (com alto contraste ativo `aplicar_tema`
  devolve `"alto_contraste"` e **não** aplica folha nem paleta: a paleta do sistema vale;
  `alto_contraste_em_vigor()` para quem desenha à mão), testes. Suíte: `ui/audit/teclado.py`
  (`_medir_o_tabuleiro`: seleciona e2 e lê o nome acessível; `CAISSA_SABOTAR_ANUNCIO=1` é a
  sabotagem), `ui/audit/capture.py` (`--escala 1.25|1.5|2` = `QT_SCALE_FACTOR` antes da
  `QApplication`; os tamanhos físicos são os mesmos, a janela é pedida em pixels lógicos e a
  recusa — a janela que não encolhe até o tamanho lógico da tela — vira `*_recusas.json`),
  `vazio` sobre as capturas físicas 3840×2160 a 200 %.
- **Briefing.** «Casa e2 selecionada» vai ao rodapé e nenhum leitor de tela ouve; nenhum
  portão roda com `QT_SCALE_FACTOR`; `grep HighContrast` não acha nada. Três itens da Carta
  §3.2 sem régua. O alto contraste **como pele nova** (contornos, sem cor como único sinal)
  é do crítico C3; aqui a régua é «a pele sai do caminho».
- **Portão.** `audit.teclado`: nome acessível do tabuleiro diz a casa selecionada e a peça
  (sabotagem: não anunciar → REPROVOU); `capture --escala 1.25/1.5/2`: a janela cabe na tela
  lógica ou o mínimo é dito com número; `vazio` a 200 % sobre 4K: ≤ 200 kpx ou o vermelho
  dito; `aplicar_tema` com alto contraste: folha vazia, paleta do sistema (teste).
- **Saída.** O leitor de tela ouve a casa; os portões medem a escala; o alto contraste do
  Windows é respeitado.

### C15 — O campo limpo: a contaminação dita, os rótulos com partição (fase 3 §0.3)

- **Arquivos.** Suíte: `benchmarks/field_exact.py` (`contaminated_diagrams` e
  `field_exact_clean` — o mesmo número sem os diagramas cujas páginas têm amostra de treino,
  `labels.pages_with_training_samples`; os dois publicados lado a lado), `docs/quality/CORPUS.md`
  (a regra). Tronco: `training.pin_field_pages` (a guarda em `resolve_splits`: rótulo novo de
  página de campo → `test`, dito no log), `data/splits.csv` (os 7 rótulos da janela sem partição
  recebem a sua por `resolve_splits`, **nunca** `train` para página de campo).
- **Briefing.** Anand 62, Euwe 25/62, Yusupov 14 e Kemeri 144 têm amostras de treino: o campo
  mede, em parte, o que o modelo viu. Publicar só o número cheio é publicar um número que
  ninguém pode conferir. E rótulos sem split ficam invisíveis a todo treino (S-56) — ou entram
  no `train` pelo próximo `cvoff-train` mesmo sendo de página de campo.
- **Portão.** Os dois números no JSON; `field_exact_clean` ≤ `field_exact` explicado por
  população; nenhum rótulo sem split; nenhum rótulo de página de campo em `train`.
  **Sabotagem:** uma página de campo marcada como de treino → `contaminated_diagrams` sobe e
  o limpo cai (teste).
- **Saída.** O campo com o seu número honesto ao lado.

### C16 — A sabotagem que faltava ao C4 (ruído de rótulo `X↔x`) e o peso da correção humana (§3.10; fase 3 §C4)

- **Arquivos.** Tronco: `dataset.py` (`BoardFenDataset.label_overrides` e `ruido_de_cor` —
  troca a cor do rótulo em `fração` das casas ocupadas dos tabuleiros de treino, semente fixa),
  `training.py` (`OptimPlan.label_noise`, `OptimPlan.corrected_repeat` — os tabuleiros de rota
  humana, `ROTAS_HUMANAS`, repetidos k vezes por época no `BoardGroupedSampler`; metadados no
  checkpoint; `train_model(label_noise=, corrected_repeat=)`), `cli/train.py`, testes. Suíte:
  `benchmarks/c4_ablation.py` (variantes `x10` = `aug0` + ruído 10 %, `w3` = `aug0` + correção
  ×3).
- **Briefing.** As sabotagens `i`/`i50` foram inertes: inverter sem trocar o rótulo não confunde
  a cor. A sabotagem honesta é trocar o **rótulo** — `X↔x` em 10 % das casas ocupadas — e ver
  se o teste 566 e o campo a acusam; se não acusam, o instrumento não tem resolução para a
  pergunta do C4 e o relatório o diz. E a pergunta que `labels.py` deixou escrita («as
  corrigidas à mão treinam melhor?») ganha um número: 161 tabuleiros de rota humana em 5.457,
  repetidos ×3, contra o `aug0` na mesma semente.
- **Portão.** `lab_gate --candidate … --runs 3` e `field_exact --model …` para `x10` e `w3`
  (semente 42, 16 épocas): `x10` **tem** de cair abaixo da faixa do `aug0` (553–556 no teste,
  1–4 exportados-e-errados no campo) — é uma sabotagem e um instrumento que não a vê é vermelho;
  `w3` é medição, não portão. Testes: o ruído só toca tabuleiros de treino; a repetição só
  conta rotas humanas; os metadados dizem os dois.
- **Saída.** A resolução do instrumento do C4 dita com número; a decisão §10.2 continua da
  pessoa, agora com o peso da correção medido.

### 3c.9 Humano (inalterado)

0b, crítico visual C3 (que agora tem o desenho dos vazios e o alto contraste como pele na
mesa), §10.2 (o `.pt`, com o C16 medido), §10.4 (perfis dos outros livros), rotular uma página
com `=` (B7).

## 3d. Fase 5 — o texto que some sem aviso, a tabela lida por coluna, a janela que não cabe, e a régua do `.pt`

A fase 4 fechou o que a análise nomeava fora da tabela. A 5 nasce do que ficou **medido e sem
dono** depois dela, e de uma releitura dos itens que mais pesam no `sol.json` publicado
(`docs/quality/sol/sol.json`, fase 4, 747 itens). Duas descobertas desta releitura, cada uma com
o comando que a reproduz:

- **A massa de erro do portão de 150 DPI é ordem, não leitura.** `scan_degraded_150` tem CER
  0,0224 contra o teto de 0,020; as seis tabelas do estrato somam 1,806 dos 3,07 de massa
  (59 %), e três delas (`table:2` 0,465, `table:4` 0,640, `table:7` 0,676) saem com **todos os
  caracteres certos** (`hypothesis_chars` = `truth_chars`) em ordem de coluna — o Tesseract em
  PSM 3 partiu a tabela em blocos por coluna e os leu um depois do outro (`scratchpad/
  probe_table.py`, blocos `b1`–`b8` com `x` disjuntos e `y` sobrepostos). As mesmas tabelas a
  300 DPI saem em ordem de linha (um bloco por célula). E a lista de lances do Dvoretsky
  (`real:…:17:401:52` 0,590, `11:54:52` 0,381, `13:278:52` 0,347): todos os lances das brancas,
  depois todos os das pretas. O RapidOCR já lê assim por linha (`engines/rapidocr.
  _reading_order`, `TABLE_CELL_CHARS`); o Tesseract não. O B1 recusa, de propósito, partir
  tabela (`max_columns=2`) e lista de lances (`min_band_chars=16`) em colunas — e deixa a
  leitura do jeito que o PSM 3 a devolveu.
- **O texto que a leitura perde é aceito.** 30 itens saem `accepted` com CER > 0,10 (foto 20,
  sombra 5, fax 4, nativo 1; massa 4,71 dos 6,19 da foto). Na foto o fundo escurece para a
  direita e o Tesseract perde o fim de toda linha (`authored:de:4`: «…im Endspiel» sem «eine
  starke»), ou quatro linhas inteiras (`synth:Dvoretsky…:201:21`: 2 de 6 linhas, aceita a 0,872,
  CER 0,786); e as variantes que as leriam (`deskew_shadow`, `bleed_sauvola`) **não rodam**,
  porque `_wants_variants` só as pede quando o original não foi aceito — e o escore não vê texto
  que falta. Medido com um protótipo (`scratchpad/probe_coverage.py`: componentes de tinta do
  tamanho de letra depois de normalizar o fundo, a fração da tinta sob as caixas de palavra):
  as leituras que perderam texto cobrem 0,21–0,85 da tinta; as boas, 0,97–1,00.

E o que as fases deixaram nomeado: o fax (fase 4 §0.3, 0,0312 → 0,0382 pelo instrumento), as
ligaduras da camada de texto (fase 4 §0.3: B12 só dobra o que os **motores** emitem — o Polgar
tem 19 em 5 páginas, `pymupdf get_text` sobre os 50 PDFs do acervo), a régua do C4 (fase 4 §C16:
a que vê o dano é a taxa de exportação e os exatos totais do campo, e a decisão §10.2 ainda não
foi posta nela), a janela que não cabe (fase 4 §C14: 1248×695 lógicos; medido de novo nesta
fase com `scratchpad/probe_minsize2.py`: **o rótulo de mensagem do rodapé é um `QLabel` comum** —
com um livro aberto, a frase do rodapé sozinha pede 1.246 px; um rótulo de estado da Rotulagem
pede 2.868 px; o cartão da Revisão de texto, 1.056), e as invariantes que toda fase roda com
exceção (`test_strings::AccentTests` e `ImpressaoDaMedicaoTests` no tronco, `test_arquitetura`
à parte na suíte). Mesmo formato: **arquivos** · **briefing** · **portão** · **sabotagem** ·
**saída**. Relatório: `docs/quality/OCR_UI_REPORT_C2_FASE5.md`. Ordem: B13 → B14 → B15 → A14 →
C17 → C18 → A15, e a crítica adversarial por último.

**O que a fase não toma, e por quê:** o `18 . . .` do Dvoretsky lido `os`/`oe`/`wee` (4 itens
nativos, um livro, uma tipografia — nomeado, não é passo); os homóglifos `Kp`/`Кр` do
`authored:ru` (3 itens, estratos degradados); o `vazio` a 200 % e o alto contraste como pele
(C3, humano); a crítica das fases 3 e 4, que não foram criticadas (fica oferecida, não tomada:
é revisão do que existe, não fase nova).

### B13 — A tabela e a lista de lances lidas por linha (o portão de 150 DPI)

- **Arquivos.** Suíte: `ocr/layout/rows.py` (novo: `rows_of_tables(result)` — os blocos do
  Tesseract que ficam **lado a lado** (`x` disjuntos, `y` sobrepostos), semeados por um bloco de
  células (mediana ≤ `TABLE_CELL_CHARS` caracteres, ou calha interna nas próprias linhas) e
  crescidos pelos vizinhos cujas linhas casam ≥ 80 % com as linhas do grupo; o grupo sai linha
  a linha, cada linha da esquerda para a direita, no lugar do primeiro bloco), `ocr/arbiter.py`
  (`ArbiterConfig.table_rows`; aplicado ao resultado de todo motor raster em PSM 1/3 — o de
  segmentação própria —, antes do escore), `ingest/pdf/ocr_service.py` (`OcrServiceConfig.
  table_rows`, um interruptor para a página e as variantes, como o `variant_dpi`),
  `benchmarks/bench_sol.py` (o interruptor pelo `SOL_CONFIG`), testes.
- **Briefing.** O PSM 3 segmenta a página em blocos; numa tabela a 150 DPI ou numa lista de
  lances de duas colunas os blocos são as colunas, e a ordem de leitura é a dos blocos — o
  texto sai certo e embaralhado (CER 0,47–0,68 com 100 % dos caracteres). A regra é a do
  RapidOCR, trazida para o Tesseract **pelos blocos dele**: um grupo de blocos lado a lado cujas
  linhas casam por altura é uma tabela e lê-se por linha; duas colunas de prosa nunca são grupo
  (linhas longas, sem calha interna, e a linha que não casa derruba o vizinho). A página de duas
  colunas de prosa não muda: o B1 a parte depois, pela calha principal, como hoje.
- **Portão.** `bench_sol` com os seis estratos: `scan_degraded_150` CER ≤ **0,020** (o portão
  absoluto do Sol que está vermelho desde a fase 1); `table:2/4/7` a 150 DPI ≤ 0,05; os três
  nativos do Dvoretsky abaixo de 0,15; `two-column` e `single` sem regressão fora do IC; ordem
  1,0000; 0 silenciosas; 0/9 controles. **Sabotagem:** `SOL_CONFIG='{"table_rows": false}'`
  devolve os números da fase 4; teste com duas colunas de prosa de linhas alinhadas → nenhum
  grupo.
- **Saída.** A tabela e a partida em duas colunas no EPUB na ordem em que se leem.

### B14 — A leitura que não cobre a tinta não é aceita, e a variante roda

- **Arquivos.** Suíte: `ocr/coverage.py` (novo: `ink_components(gray, dpi)` — fundo estimado por
  fechamento morfológico, tinta forte abaixo de uma fração do fundo, componentes do tamanho de
  letra; `ink_coverage(result, components, box)` — a área de tinta cujo centro cai numa caixa
  de palavra, sobre a tinta da região, fora das caixas de diagrama), `ingest/pdf/ocr_service.py`
  (`OcrServiceConfig.ink_coverage` e `min_ink_coverage`; em `_wants_variants` a cobertura baixa
  pede as variantes mesmo com o original aceito; em `_settle` a leitura incompleta não ancora
  quando há uma completa, e nenhuma incompleta sai `ACCEPTED` — vira `REVIEW` com «a leitura
  cobre N % da tinta da região»), `benchmarks/bench_sol.py` (a coluna «aceitos errados» — aceitos
  com CER > 0,10 — por estrato), `benchmarks/calibrate_sol.py` ou script próprio para ajustar
  `min_ink_coverage` **só na partição `calib`**, testes.
- **Briefing.** O escore da arbitragem é confiança por palavra, plausibilidade e concordância —
  nada nele diz quanto da página ficou sem ler. Uma leitura que perdeu metade das linhas pode ter
  confiança 0,87 nas que leu, e é aceita; as variantes que leriam o resto (a normalização de
  sombra, o Sauvola) só rodam quando o original é recusado. A cobertura da tinta é o sinal que
  faltava: é barata (uma passada morfológica por página), não depende de idioma, e o protótipo
  separa as leituras incompletas (0,21–0,85) das boas (0,97–1,00). Só leituras de raster; a
  camada de texto é «o que o PDF diz».
- **Portão.** `bench_sol` com os seis estratos: aceitos com CER > 0,10 caem de **30** (e nenhum
  estrato sobe); `photo` CER abaixo de 0,0983 fora do IC; os outros estratos sem regressão fora
  do IC; 0 silenciosas; 0/9 controles; `s/MP` dito (as variantes rodam mais). **Sabotagem:**
  `SOL_CONFIG='{"ink_coverage": false}'` devolve os 30; teste com uma leitura que perdeu as
  últimas linhas → `REVIEW`, e com diagrama na página → a tinta do diagrama não conta.
- **Saída.** O texto que se perdeu vai para a revisão com a razão, em vez de entrar no livro
  como se estivesse inteiro — e, quando uma variante o lê inteiro, entra inteiro.

### B15 — O fax, depois do B14

- **Arquivos.** Suíte: `ocr/portfolio.py`/`ingest/pdf/ocr_service.py` só se o número pedir.
- **Briefing.** A fase 4 nomeou «fax/pontilhado → upscale + segundo motor» com o ganho conhecido
  (0,0382 → 0,0312). Dos 4 aceitos errados do fax, o `authored:en:21` perdeu uma linha inteira
  (RapidOCR 0,847 de cobertura) — é o B14. Mede-se o fax depois do B14; a rota pelo sinal de
  pontilhado só entra se o B14 não devolver o número, e com o seu próprio A/B.
- **Portão.** `fax_dither` CER ≤ 0,0312 ou a razão medida de não chegar lá. **Sabotagem:** a
  do passo que entrar.
- **Saída.** O fax com o número que o produto paga, dito.

### A14 — As ligaduras da camada de texto

- **Arquivos.** Suíte: `ingest/pdf/textlayer.py` (o texto de todo span passa por
  `engines/normalize.fold_ligatures` — a mesma tabela de sete, **não** NFKC), testes.
- **Briefing.** O B12 dobrou `ﬁ ﬂ ﬀ ﬃ ﬄ ﬅ ﬆ` na saída dos motores; a camada de texto ficou «o que
  o PDF diz». No acervo, o Polgar tem 19 ligaduras em 5 páginas: entram no IR, no EPUB e na
  busca como U+FB01 (um leitor de tela lê «fi» como um caractere desconhecido, a busca por
  «first» não acha «ﬁrst»).
- **Portão.** Importar as 5 páginas do Polgar: 0 pontos de código U+FB00–FB06 no IR; teste de
  fronteira (`½`, `²`, `№` ficam). **Sabotagem:** sem a dobra → as 19 voltam (teste).
- **Saída.** O IR sem ligaduras também quando o texto vem do PDF.

### C17 — A régua do campo para a decisão do `.pt` (§10.2)

- **Arquivos.** Tronco: `field_eval.py` (`FieldReport.diagrams`: por diagrama casado, livro,
  página, índice, `legal`, `gate_confidence`, exato na régua anotada e contaminado — somado por
  `_accumulate`). Suíte: `benchmarks/field_exact.py` (`--por-diagrama` grava as linhas no JSON),
  `benchmarks/model_ruler.py` (novo: para cada modelo, a curva risco × cobertura do campo — para
  cada limiar do gate, exportados e exportados-errados —, os exatos totais, e os exportados
  exatos com no máximo 0/1/2 errados), testes.
- **Briefing.** A fase 3 comparou as variantes do C4 pelo laboratório e pelos exportados-errados
  num ponto (gate 0,80); a fase 4 mostrou que essas réguas são cegas ao dano (o `x10` exporta 72
  em vez de 104 com o **mesmo** laboratório) e que um modelo menos confiante não é pior, é outra
  escala. Comparar modelos num limiar fixo é comparar escalas. A régua certa é a curva: quantos
  diagramas certos cada modelo entrega com 0, 1 ou 2 errados no PDF. É medição sobre os
  checkpoints que já existem (produção, `c4_{aug0,mhsp,mhspe,e}_s4{2,3,4}`, `x10`, `w3`) —
  nenhum treino; a troca continua da pessoa.
- **Portão.** A tabela para todos os modelos, com os números do ponto de gate idênticos aos
  `field_exact` publicados (produção 103 exportados, 102/103 na régua corrigida). **Sabotagem:**
  uma curva com os rótulos de exatidão embaralhados (semente fixa) não pode ordenar os modelos
  como a verdadeira (teste).
- **Saída.** A decisão §10.2 com a régua que vê o dano.

### C18 — A janela cabe no portátil

- **Arquivos.** Tronco: `qt/rodape.py` (a mensagem num `RotuloElidido` — a frase inteira na dica
  e na lista das últimas 50), o que mais o probe apontar nos painéis do tronco. Suíte:
  `ui/views/rotulagem.py`, `ui/views/revisao_de_texto.py`, `ui/widgets/cartao_da_linha.py` (os
  rótulos de estado e de cartão elididos ou com quebra), `ui/audit/capture.py` (ou um arnês
  próprio: o mínimo da janela em toda área, nas três peles, com e sem livro, e com uma mensagem
  de 300 caracteres no rodapé), testes.
- **Briefing.** Um `QLabel` comum pede como largura mínima o texto inteiro. O tronco já resolveu
  isso para o nome do livro (`RotuloElidido`, F9-C2) e esqueceu a mensagem do rodapé, que é o
  texto mais variável da janela: cada frase longa empurra a janela para fora da tela. E as abas
  da suíte têm os seus. A fase 4 mediu 1248×695 lógicos; a área de trabalho de um portátil
  1920×1080 a 150 % (a configuração de fábrica mais comum em 14") é 1280×672 menos a barra de
  título.
- **Portão.** O mínimo da janela ≤ **1250×640** lógicos em toda área, nas três peles, com e sem
  livro, e com a mensagem de 300 caracteres (cabe em 1920×1080 a 150 % e em 1366×768 a 100 %);
  o mínimo a 125 % sobre 1366×768 dito com número. **Sabotagem:** a mensagem num `QLabel` comum
  → o mínimo sobe e o portão reprova.
- **Saída.** Uma frase longa no rodapé nunca mais decide o tamanho da janela.

### A15 — As invariantes num comando só

- **Arquivos.** Tronco: `tests/test_strings.py` (os identificadores que não são texto de
  interface — `configuracoes` de comando, `SELECAO` de token, `pagina` de chave, a lista de
  palavras-vazias — fora da régua de acento, com a razão), os relatórios de campo correntes
  remedidos (`cvoff-field --json`) para o `ImpressaoDaMedicaoTests` passar sem `--deselect`.
  Suíte: `tests/unit/ui/test_arquitetura.py` num subprocesso próprio (a afirmação «nenhum
  binding de Qt em `sys.modules`» é sobre um processo novo, e o teste passa a criá-lo), o
  `sol.json` publicado medido no commit da fase.
- **Briefing.** Cada relatório de fase repete «1 reprovado pré-existente», «um `--deselect`», «à
  parte». Uma invariante com exceção é uma invariante que ninguém confere; a fase 5 deixa os dois
  comandos do §0 verdes sem exceção.
- **Portão.** `pytest` do tronco sem `--deselect` e sem reprovado; `pytest` da suíte com PyQt6 e
  **com** `test_arquitetura.py` na mesma corrida, 0 reprovado. **Sabotagem:** um `import PyQt6`
  no arnês de auditoria reprova o `test_arquitetura` no subprocesso (hoje só reprova sozinho).
- **Saída.** O §0 deste roadmap sem asterisco.

### 3d.8 Crítica

Um crítico adversarial (Claude, `CRITIC_CHARTER.md`) sobre os commits da fase, com os portões
reproduzidos por ele; o veredito transcrito em `OCR_UI_ANALISE_C2_CRITICAS.md` («Fase 5»).

### 3d.9 Humano (inalterado)

0b, crítico visual C3, §10.2 (agora com a régua do C17), §10.4, rotular uma página com `=`.

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
| 2026-09-21 | C8 | **o `Tab` percorre as duvidosas uma vez e sai** (`proxima_duvidosa(dar_a_volta=False)`; `focusInEvent` por `Tab` pousa na primeira) | A volta era uma armadilha de teclado (WCAG 2.1.2): com uma posição na tela o tabuleiro consumia todo `Tab`/`Shift+Tab`/`Ctrl+Tab`. A auditoria `teclado` mede a cadeia pelo `focusNextPrevChild` da janela e não a via. Revisão do construtor antes da crítica (tronco 545ce67); `percurso --teclado` 2 teclas PASSOU, sabotagem REPROVOU, `audit.teclado` PASSOU | construtor |
| 2026-09-21 | C8 | **`trilho.aprendeu` afirmado só com hesitante na página** | No Aagaard 31–38 os 13 diagramas leem com folga; a dúvida do trilho é de texto e a correção de um diagrama não a muda — afirmar `aprendeu` ali seria afirmar o que a página não tem. O fluxo `livro` diz em nota; a regra fica no `test_trilho` (hesitante → decidido) e no `PonteTests` | construtor |
| 2026-09-21 | C9 | **`regiao_selecionada` → `TRACEJADO`** | O papel `ALVO` da pele media 1,65:1 sobre a página na auditoria de contraste (o par da suíte reprovava); o tracejado é o traço de seleção que a pele já tem sob portão | construtor |
| 2026-09-21 | C9 | **palavras fracas do cartão na letra, não no fundo** (`cartao_palavra_conferir` = `ATENCAO`, `cartao_palavra_revisar` = `PROBLEMA_TEXTO`) | A primeira versão mapeava os fundos âmbar/vermelho do cartão para `REALCE_NOTA`/`REALCE_DESTAQUE`, que na tabela de significado do tronco são o canal de **quem escreve** (`REALCE_NOTA` é verde): a suíte inteira acusou `#b9ffc5` atrás de uma palavra duvidosa. A regra do editor do tronco (`ui/texto_cores.py`) é confiança na letra; `contraste` remedido 308/228 PASSOU com os 8 pares | construtor |
| 2026-09-21 | C10 | **o recorte vira pelo mesmo critério do tabuleiro** (`recorte.mostrar(virado=pretas)`) | No ponto de vista das pretas a casa canônica `i` está impressa em `63 − i`, como na leitura de cabeça para baixo; o recorte virava só por `rotation == 180` e a tinta/o clique caíam na casa espelhada. Revisão do construtor antes da crítica; `PontoDeVistaDasPretasTests` (2) | construtor |
| 2026-09-21 | C2/C3 | **tarefas do aquecimento e da segunda opinião sem pai** (`manter_viva`); **parecer por identidade do diagrama** | Filhas do painel/janela, eram destruídas com eles e o destrutor de `QThread` aborta o processo com a thread a correr (F9-C2); o parecer conferido só pelo índice ia parar no diagrama de mesmo índice da página seguinte (S-68). Revisão do construtor antes da crítica (tronco be790f0); 3 testes | construtor |
| 2026-09-21 | B2/B6 | **as faixas na escala do Tesseract** (`arbiter.SCALE_OF`, `calibration_for` na pontuação e na fusão) | Crítico Codex (fase 2, ciclo 1, bloqueante 1): `tesseract_strips` não tinha tabela e ficava na escala crua enquanto a âncora era calibrada — a incompatibilidade que o B6 tira. Medido no commit final (`f3_*`): nenhum item muda | construtor + crítico |
| 2026-09-21 | fase 2 | **benchmarks remedidos no commit final** (`f3_on`, `f3_b1_off`, `f3_b2_off`, `commit 3bbcf23`) | Crítico Codex (bloqueante 2): os `f2_*` registravam `beb8a71`, a árvore antes do commit. CER e lances idênticos ao milésimo; `s/MP` 10–20 % maior em todas as configurações (máquina, não código); uma corrida por configuração pela determinismo demonstrada (B9 274/274; `f3` = `f2`) | construtor + crítico |
| 2026-09-21 | C2 | **a tarefa de `_rodar` sem pai; `Aquecimento.cancelar` ao fechar** | Crítico Codex (bloqueante 4): o `closeEvent` aceitava o fecho com a thread viva depois de 15 s — abort do `QThread`. `manter_viva` + `_se_viva`; e o relógio de uma janela fechada-mas-não-destruída disparava o aquecimento numa janela morta (portão de execução do tronco) | construtor + crítico |
| 2026-09-21 | B1/B2 | **falhas ditas nas notas**: faixa que falha → `PageRecognition.notes`; leiaute em scan que falha → `PageOutcome.notes` | Crítico Codex (bloqueante 5 e não bloqueante): `debug` e silêncio; o pipeline seguia como se o passo não existisse | construtor + crítico |
| 2026-09-21 | B1 | **`_slice` por palavra** | Revisão do construtor: uma linha que o PSM 3 fundiu pela calha tem o centro numa das colunas e caía inteira nela, levando as palavras da outra como apoio da fusão. Medido: nenhum item muda | construtor |
| 2026-09-21 | C9 | **reserva clara da região `#7c3aed` → `#8b5cf6`** e teste das reservas | Sem o tronco ninguém media as reservas: 2,99:1 sobre a folha, piso 3,0 | construtor |
| 2026-09-21 | B3/C3 | **`CAISSA_FIGURINE_TESSDATA` só no `bench_sol`** | Com a variável no ambiente o `config` do tronco recusa o caminho e o classificador de diagramas não carrega — o portão do B3 (partidas sob diagramas) contava 0 partidas por isso, não pelos NAGs. Portões que precisam de diagramas lidos correm sem ela | construtor |
| 2026-09-21 | C4 | **`RandomStroke` a 1 px, não «1–2 px»** (`AugmentConfig.stroke_px=(1, 1)`) | Medido em 36 casas reais do Koblenz, Burgess e Euwe antes de treinar: a dilatação de 2 px fecha o contorno das brancas (fração clara dentro do glifo 0,84 → 0,34, mínimo 0,04 — uma torre branca em casa hachurada vira um bloco preto) e a erosão de 2 px apaga as pretas (preenchimento mínimo 0,03). Com 1 px o contorno continua contorno (0,57, mínimo 0,20). Dois pixels trocariam o rótulo; teste com contorno sintético para os dois raios | construtor |
| 2026-09-21 | C4 | **piso do cache por processo na janela do amostrador** (`training.Trainer.prepare`) | 128 ÷ 5 = 25 tabuleiros por worker para uma janela de 64: cada casa reabria o PNG. Medido nesta máquina (GPU): 10,1 min/época com 25, **3,2 min** com 64 (`loader_probe`, 400 lotes 111 s → 35 s). Sem isso a ablação de 4 variantes × 16 épocas custaria 11 h; com, 2 h. Teste `test_the_per_process_cache_never_drops_below_the_sampler_window` | construtor |
| 2026-09-21 | C4 | **a janela retreina no regime do checkpoint** (`TrainingRequest.augment` ← `augment.version_of_checkpoint`) | A janela treinava sempre `AugmentConfig()` (análise §3.4): se o `.pt` de produção virar `mhspe`, o retreino da janela o devolveria ao genérico em silêncio. O regime é lido do checkpoint no clique; `from_letters` é a inversa de `AugmentConfig.version` | construtor |
| 2026-09-21 | B10 | **a maioria não moveu nada; estilo ou janela movem +3** (914 → 917 no Gaprindashvili) | Cada mecanismo tem interruptor (`cipher_style`, `cipher_window`, `cipher_majority`) e sabotagem no `--what contest`: `cifra_plana` devolve 914; estilo só, janela só e maioria só dão 917 cada — o símbolo resgatado é provado tanto pelo estilo como pela janela. A maioria fica (as tabelas do corpus têm 13 linhas em que a primeira observação era a errada — `'it` Q×3 contra K×26 — e o formato 1 nunca as provaria), sem número a seu favor nestas páginas | construtor |
| 2026-09-21 | C11 | **uma linha de um lance só confirma, nunca troca; a segunda opção só em casa hesitante (margem < 0,9), a cor em qualquer casa** (`lance_seguinte.MIN_LANCES_PARA_REPARO`, `MARGEM_HESITANTE`, `_candidatas`) | Na primeira versão a busca tentava a segunda opção de qualquer casa: com a matriz sintética do teste, uma casa **vazia a 0,99** virava dama porque o lance fecharia — e dois candidatos empatavam. A segunda opção de uma casa segura é ruído; a **cor** da mesma peça é o erro que o campo mede (10 de 27) e vale em qualquer casa. Testes `test_an_empty_confident_square_is_never_filled`, `test_a_confident_piece_may_only_change_colour` | construtor |
| 2026-09-21 | C11 | **população 2 no campo**: `next_move_checked` 2 de 114, `lance_vizinho` inerte | O conjunto de campo é de livros de problemas e exercícios: dois diagramas têm linha de lances sob eles. O portão (b) não tem resolução no campo e o relatório o diz; a mecânica fica pelos 11 testes e o portão (a) pelo `lab_gate` (0,9770 → 0,9806, `helped` 2, `hurt` 0) | construtor |
| 2026-09-21 | C5 | **amostras por peça e por cor da casa; extremos com margem de 10 e só com as cores separadas, aparada uma amostra de cada lado; mínimo 5; o tabuleiro não é amostra de si** (`cor_por_livro.chave_da_amostra`, `MARGEM`, `MINIMO_POR_COR`, `_aparadas`, `decidir`) | Cinco rodadas do «um de fora de cada vez» nos 22 Koblenz corrigidos, cada uma custou uma versão: (1) todas as peças juntas com quantis p5/p95 → 7 de 15 trocas erradas (um rei branco no p5 dos reis brancos é trocado por definição); (2) por tipo → um cavalo branco (crina escura, 159) e uma torre preta (ameias claras) trocados; (3) extremos com margem → um cavalo com **4** amostras; (4) por cor da casa → a torre branca a 151 em casa clara, abaixo da branca mais escura e **dentro** das pretas (136–224: as p. 46–48 imprimem as pretas hachuradas); (5) *como* separar, medido três vezes — extremos, mediana ± 2 MAD, aparada uma amostra de cada lado: as duas primeiras rodadas ainda tinham os tabuleiros da página de campo no conjunto (o erro de base da página, linha abaixo) e nelas o MAD calava as damas de casa clara; **com a retenção certa as três dão o mesmo 6/6** (`scratchpad/loo_variants.py`). Fica a aparada pelo teste sintético (uma hachurada não cala as outras; duas, a cor não separa) — por argumento, não por número. Final: **6 trocas, 6 certas** (k = 22); 0 com k = 6 ou 12. O próprio tabuleiro pediu `b2 P→p` no Stefaniu (peões brancos de casas escuras contra os de casas claras) — tirado | construtor |
| 2026-09-21 | C6 | **as páginas do conjunto de campo são retidas como as cegas** (`closing.field_pages_of`) | A primeira aprovação do perfil do Koblenz levou as duas amostras da p. 50 — página de campo — e o `field_exact` teria medido o próprio perfil. A regra é a de `CORPUS.md` 5.3 no sentido inverso: o campo mede, nunca alimenta. O contador `diagrams_withheld` os soma às cegas | construtor |
| 2026-09-21 | A11 | **um sidecar para os dois PGNs** (aceitos e revisão na mesma lista, com o veredito por linha) | Dois sidecars com a mesma chave seriam a colisão que `verificar` existe para acusar; o `.review.pgn` aponta para o mesmo arquivo. O teste de retomada (`test_resume_produces_the_same_pgn`) passou a normalizar o nome do sidecar — único header que difere entre `inteiro.pgn` e `retomado.pgn` | construtor |
| 2026-09-21 | B10 | **a origem da figurina vai em `TextSpan.figurine_origin`, não em `engine`** | `test_a_scan_without_a_text_layer_is_read_by_default` (Sol §SOL-1) acusou a primeira versão na suíte inteira: com a origem no `engine`, um parágrafo do Flores Rios saía `glyph+tesseract+tesseract_figurine` e cinco linhas só de lances saíam `glyph`. A proveniência do bloco é do OCR que leu as palavras; quem pôs a peça é a do `PieceGlyph` (`note`). `test_figurine_provenance` reescrito: os cinco spans com `engine` `tesseract` e `figurine_origin` `"", glyph, "", cifra, ""` | construtor |
| 2026-09-21 | C6 | **`source_page` do `labels.csv` é base 1; o fechamento o converte antes de reter** (`closing._page_index_of_label`) | A segunda aprovação do perfil do Koblenz ainda levava os dois tabuleiros da página de campo 50: o tronco grava a página como a janela mostra (base 1, `51`; `labels.pages_with_training_samples` subtrai um), e o campo, o manifesto cego e as decisões são base 0 — a retenção comparava `51` com `50`, retinha dois tabuleiros da p. 49 (índice) e deixava entrar os da página de campo. Apareceu ao listar as seis trocas do um-de-fora casa a casa (`p51 h4 Q→q` era o `p50 d0` do campo). Perfil apagado e aprovado de novo (152/150 amostras, 6 trocas, 6 certas), campo remedido; teste com o rótulo `13` contra a página de campo `13` | construtor |
| 2026-09-21 | C4 | **as sabotagens `i` (3 %) e `i50` (50 %) são inertes; a próxima é ruído de rótulo `X↔x`** (`c4_ablation.SABOTAGE_VARIANTS`) | `c4_i_s42` = `aug0` no teste (556/566) e no campo (4 casas de cor contra 5); `c4_i50_s42` 553 no teste (a faixa do `aug0` é 553–556) e 7 casas de cor contra 5–8, com menos exportados-e-errados (2). Inverter o contraste sem trocar o rótulo não confunde a cor: o fundo invertido é um modo à parte que o modelo separa. Uma sabotagem que não piora não prova o instrumento — fica vermelha no relatório, com a próxima desenhada: trocar `X↔x` em 10 % das casas rotuladas | construtor |
| 2026-09-21 | C4 | **nenhuma variante domina em três sementes; o `.pt` fica** | `aug0` 556/553/555 no teste e 3/4/1 exportados-e-errados no campo (0,9712/0,9608/0,9901); `mhspe` 553/555/554 e 4/4/2 — médias 554,7 × 554,0 e 2,7 × 3,3: a variância entre sementes é maior que a diferença entre variantes, e o traço fica um pouco abaixo em tudo. `mhsp` ≈ `aug0`, `e` ≈ `mhspe`; 0 ilegais e `hurt` 0 em todos. O 1 tabuleiro de validação (518 × 517 de 535) do `RandomStroke` não sobrevive ao teste nem ao campo. Os candidatos leem as damas do Koblenz porque 14 tabuleiros do livro entraram em `train` em 2026-09-20 — não é o aumento (o `aug0` também lê) e a comparação justa é candidato × candidato | construtor |
| 2026-09-21 | C12 | **«mate em N» é mate em exatamente N** (`estipulacao.verificar`: um mate mais curto devolve `fecha=False` com «mais curto que a exigência») | Na primeira versão um mate em 1 «fechava» uma exigência de 2, e na busca de trocas uma peça a mais fechava por um mate que o problema nunca teve — o teste do empate ganhou uma terceira vencedora. Um mate mais curto é cozido ou leitura errada, e é dito | construtor |
| 2026-09-21 | C12 | **a busca de trocas só com a busca exaustiva (mate ≤ 2), nunca com o motor nem com mate em 1** (`LANCES_DA_BUSCA`, `MIN_LANCES_PARA_REPARO`) | Cada verificação no motor custa até 3 s; 38 candidatas numa página de seis problemas travariam a janela. Mate em 1 é a regra «um lance só confirma» do C11 | construtor |
| 2026-09-21 | C12 | **o motor fecha antes do `join` das threads** (`estipulacao.registrar_fecho` com `threading._register_atexit`) | O `SimpleEngine` do python-chess corre numa thread que não é *daemon* e o interpretador a junta antes dos `atexit`: o `field_exact` imprimia o relatório e ficava pendurado (duas corridas mortas à mão) | construtor |
| 2026-09-21 | C12 | **portão (a) achou duas anotações erradas no conjunto de campo** (Niemeijer p20 d0 e d2) | d0: a verdade anotada tem mate em 1 para um `3‡` cuja chave impressa (`1.Pd3`) nem é legal nela — a fila 5 está deslocada uma coluna na anotação (imagem com grade); d2: a anotação diz torre branca em h1, a leitura da máquina (torre preta, «exportada e errada» a 0,805) fecha o `3+` com o `1.Kb7` que o livro imprime — entrou em `field_corrections.json` com a prova documental e o glifo; d0 fica para olho humano (a fila corrigida ainda tem mate em 2) | construtor |
| 2026-09-21 | C12 | **`estipulacao_vizinha` é sabotagem fraca nesta população** | Numa página de problemas a exigência é a da página (Polgar: seis `#2`); a rotação só muda 2 de 10 e devolve os mesmos contadores (`truth 8/10` × `9/10`). A que reprova o portão é `sem_estipulacao` (`checked 0`) | construtor |
| 2026-09-21 | A12 | **o portão achou 4 erros no EPUB do produto** (`OPF-028: prefixo não declarado "pdf"`) | `percurso --fluxo livro` validou o EPUB exportado pela janela: as entradas `MetadataEntry(scheme="pdf")` do importador saíam como `property="pdf:Producer"` sem prefixo no `<package>` — invisível ao corpus dos testes, que não tem entrada assim. Todo esquema de metadado vira prefixo declarado (`_prefix_token`) e o nome vira termo válido (`_property_token`); teste com EPUBCheck | construtor |
| 2026-09-21 | A12 | **EPUBCheck que não roda devolve `-1`, nunca «0 erros»** (`run_epubcheck`) | Um arquivo inexistente saía com «0 erros fatais / 0 erros» e código 1 — o antigo helper lia 0. O resumo é lido nas duas línguas, os fatais somam, e sem resumo com código ≠ 0 é falha | construtor |
| 2026-09-21 | B11 | **o teto físico não reproduz «5 px» na fonte sintética** | Com a fonte do arnês o teto relativo em 382 px dá 0,0 (sobram < 20 componentes), não 5 px como nos itens reais: a mesma falha (o que sobra não é letra). O teste afirma «solto = folha» com o físico e «solto ≠ folha» com o relativo; a mudança de rota é medida no benchmark | construtor |
| 2026-09-21 | C14 | **o PyQt6 não expõe `QAccessible`; o anúncio é o `setAccessibleName`** | O roadmap pedia `QAccessible.updateAccessibility`; o binding não o tem. O próprio `QWidget.setAccessibleName` emite o `NameChanged`; anunciado só quando muda | construtor |
| 2026-09-21 | C14 | **a janela exige 1248×695 lógicos** (`capture --escala`, `*_recusas.json`) | A 125 % não cabe em 1366×768 nem 1280×800; a 150 % só em ≥ 1920×1080; a 200 % só em 4K. E a 200 % sobre 4K, 6 de 8 painéis passam de 200 kpx (`vazio`). Dois números novos e vermelhos para o crítico C3 | construtor |
| 2026-09-21 | C14 | **alto contraste = «a pele sai do caminho»**, não «≥ 7:1 medido» | Não há como medir a paleta de alto contraste do Windows *offscreen*; a régua honesta é que `aplicar_tema` não aplica folha nem paleta com o modo ligado (teste). Contornos e papéis sem cor são pele nova: C3 | construtor |
| 2026-09-21 | C15 | **rótulo novo de página de campo vai para `test`, dito** (`training.pin_field_pages`) | O sorteio poria os dois Koblenz «51» (página de campo 50) em `train`/`val`; `test` é retido como o campo. O split `test` passa de 566 a 569 — o `aug0` s42 foi remedido nele para a comparação do C16 valer | construtor |
| 2026-09-21 | C16 | **10 % de ruído de rótulo quase não aparece no laboratório e aparece inteiro no campo** (`x10` 557/569 × `aug0` 558/569 no teste; **72 × 104 exportados** no campo) | A rede treinada com rótulo sujo fica menos confiante e o gate de 0,80 barra 32 diagramas que antes passavam — e o que passa é todo exato (72/72), com 108 exatos no total contra 103. A régua da fase 3 para o C4 (`board_exact` do teste + exportados-e-errados) era cega ao dano; a que o vê é a taxa de exportação e os exatos totais do campo. `x25` fica na tabela (`LABEL_NOISE_VARIANTS`) para quem quiser a curva | construtor |
| 2026-09-23 | fase 5 | **a fila de A/B carrega o `SOL_CONFIG` de todos os interruptores da fase** | A primeira fila do B13 começou antes de o B14 existir; o processo `off`, nascendo depois, teria o B14 ligado — a comparação mediria duas coisas. Parada e refeita inteira no código final, cada corrida com `{"table_rows": …, "ink_coverage": …}` explícito | construtor |
| 2026-09-23 | B13 | **a coluna de células mais alta semeia o grupo** (`rows.table_groups`) | Em ordem de leitura, as duas células de uma linha só da última fila do `table:4` a 150 DPI formavam um grupo próprio e a linha saía partida (CER 0,033 → 0,0036 com a ordem nova); teste `test_the_tallest_column_of_cells_seeds_the_table` | construtor |
| 2026-09-23 | B13 | **duas regras medidas em página real, não no corpus: a coluna de células não tem linha de prosa, e o grupo não cruza a calha da página** (`rows._is_cells`, `rows._is_column_gutter`) | Os itens de tabela do corpus são recortes. Na página inteira de duas colunas do Levenfis, o bloco da coluna direita (lances curtos e uma linha de prosa, com calha interna) e o ruído lido num diagrama da coluna esquerda semearam grupos que puxaram uma coluna para o meio da outra (p. 40 similaridade 0,857 com o desligado, p. 41 0,290). Teto de 24 caracteres na linha de célula, e a calha: um corredor de ≥ 8 px que ≤ 10 % das linhas **de prosa** que alcançam os dois blocos tocam. Contar toda linha desfez o `table:4` a 150 DPI (nada cruza o vão entre as colunas de uma tabela: 0,0036 → 0,64), medido e travado por teste. Final: os seis itens do corpus como antes; Levenfis 36–52, Estrin 20–27 e Stefaniu 40–47: 28 de 33 páginas idênticas, as outras com a lista de lances lida por linha ou o ruído de um diagrama reordenado (`OCR_UI_REPORT_C2_FASE5.md` §B13) | construtor |
| 2026-09-23 | B14 | **a tinta é letra medida em polegadas, em linha de texto, e cada letra pesa um** (`coverage.ink_map`) | A revisão do construtor com páginas sintéticas achou dois sequestros antes do benchmark: meio-tom (milhares de pontos de 5 px puxaram a mediana e as letras viraram «grandes demais»: cobertura 0,009 numa página lida inteira) e tom contínuo com manchas do tamanho de letra (0,64–0,72). Teto físico do B11, corridas esfregadas que são linhas (largas, baixas, densas) e contagem por letra: 1,00 nos dois, e a leitura que perdeu 3 de 5 linhas segue em 0,40. O primeiro A/B do B14 (medida ingênua) foi descartado | construtor |
| 2026-09-23 | B14 | **o piso 0,90 reajustado na `calib` com a medida final** (`benchmarks/fit_ink_coverage.py`) | Com a medida refinada a `calib` não separa os pisos de (0,8756; 0,9000]: todos sinalizam as mesmas seis leituras (6/16 perdidas, 0/182 boas, 6/8 aceitas-perdidas); 0,90, o do primeiro ajuste, está no intervalo e fica. A `dev`, só conferida: 21/30 perdidas e 17/21 aceitas-perdidas sinalizadas, 0/359 boas. Na população real (Estrin, Levenfis, Stefaniu pelo importador, 504 regiões medidas) nenhuma região sinalizada | construtor |
| 2026-09-23 | A14 | **premissa corrigida: o IR do importador já saía sem ligaduras** | `textlayer._text_flags` sempre desligou `TEXT_PRESERVE_LIGATURES`; os três leitores da camada que não desligavam eram o nível 0 (6 + 5 ligaduras nas p. 6 e 9 do Polgar, e o `recognize_page` nem passa pela dobra do B12), as linhas de leiaute por página e o índice de busca. Bandeiras em vez de `fold_result`: o MuPDF divide a caixa da ligadura entre as letras, e o nível 0 guarda caixa por caractere | construtor |
| 2026-09-23 | C18 | **o mínimo medido com as áreas visitadas: 1538×659, não 1248×695** (`caissa.ui.audit.minimo`) | A recusa do `capture --escala` é lida antes de as áreas serem mostradas. Com elas visitadas e um livro aberto, o motor da largura era a barra de anotação sob o visor (810 px na Foco), não o visor; e a frase do rodapé num `QLabel` comum pedia 1.246. A altura vinha do Resultado (520) e, depois dele, da Galeria do tronco (516: é ela que segura a pele Foco em 640, no teto) | construtor |
| 2026-09-23 | C18 | **o arnês encerra o processo de trabalho antes do `os._exit`** | Fechar a janela com a leitura do Dataset viva derruba o interpretador (`access violation`, medido), então o arnês sai sem desmontar — e o filho `spawn` do `processo_de_trabalho` não morre com o pai no Windows: seis órfãos vivos, um deles segurando a medição seguinte por minutos | construtor |
| 2026-09-23 | A15 | **acentos: regras por posição, nenhuma palavra permitida a mais** (`test_strings._literais_visiveis`) | Os seis vermelhos eram identificadores (id de comando, chave de JSON gravado, `SELECAO = "SELECAO"`, palavras dobradas para `.split()`). Pôr `pagina`/`configuracoes` em `PERMITIDOS` deixaria passar o texto de tela; as regras olham a posição do literal e um teste prova que o texto de tela nas mesmas construções continua varrido | construtor |
| 2026-09-23 | B13 | **crítico, ciclo 1: prosa por palavras, uma numeração por grupo, a calha da página com prosa de um lado, calha interna mais larga que um espaço, e adjacência** (`rows._is_prose`, `_numbers_moves`, `_page_gutters`, `_cell_gaps`, `_adjacent`) | O crítico reprovou com páginas reais de colunas estreitas: a Gallagher p. 50 (22–27 caracteres por linha, nenhuma linha de prosa por comprimento, a calha nunca julgada) foi a CER 0,27 → 0,70 pelo importador, a p. 53 pôs o cabeçalho de outra partida nas notas, e duas páginas construídas de partidas numeradas se embaralharam. Cada regra veio do caso que a pedia (a Kmoch p. 44: um parágrafo com uma calha espúria; a Gallagher p. 52: «The | so-called | “Long» em três blocos) e tem teste com sabotagem; os sete itens do corpus ficam como antes, a Gallagher p. 50 passa a **melhorar** (0,2732 → 0,2028) | construtor + crítico |
| 2026-09-23 | B14 | **crítico, ciclo 1: a moldura do scanner não é «coisa grande», a região não medida é dita, e o desempate do piso é escrito** | Um componente com a caixa de metade da imagem ou mais é a borda do scanner: dentro dela está a página (Kmoch pp. 40/44/48: 0 letras → 1.058/1.162/995). O rastro diz «cobertura da tinta não medida» em vez de calar. O piso: a `calib` não separa os pisos de 0,8757 a 0,99 pela regra do máximo de aceitas-perdidas sem boa sinalizada; o desempate, escrito **depois** de a `dev` ter sido vista (dito assim), é o menor piso na grade de décimos que atinge o máximo -- 0,9, o mesmo número; na grade de centésimos seria 0,88 (`dev`: 15/21 aceitas-perdidas em vez de 17/21, 0/359 boas nos dois). A resolução de décimos é a que 16 leituras perdidas sustentam | construtor + crítico |
| 2026-09-23 | C17 | **crítico, ciclo 1: os orçamentos em todo valor distinto de confiança, e a AURC média sobre as ordens dos empates** (`model_ruler.cuts`, `aurc`) | A grade de limiares parava em 0,99: o errado da produção está a 0,9979 com 74 exatos acima, e a coluna «≤ 0 errados» saía 0 em seis modelos (produção 0 → 74; `mhsp_s43` 43, `mhspe_s43` 43, `mhspe_s44` 38, `e_s43` 31, `e_s44` 27). A AURC dependia da ordem dentro dos empates (`c4_mhspe_s44` 0,0111–0,0134). A tabela e as conclusões do §C17 foram refeitas sobre as mesmas linhas | construtor + crítico |
| 2026-09-23 | C18 | **crítico, ciclo 1: caber não basta -- o portão mede o que fica à vista** (`caissa.ui.audit.minimo`: fora da vista sem barra, espremido abaixo de 90 % do mínimo, mensagem do rodapé ≥ 320 px com o nome de 149 caracteres; sabotagens `corte` e `mensagem`) | As rolagens da primeira versão desligavam a barra horizontal e a janela «cabia» escondendo: a barra de ações do Resultado e «Pular/Anterior/Próxima» da Revisão de texto com 0 px à vista, a mensagem do rodapé com 0 px ao lado do nome longo (o Qt encolhe primeiro o item esticável). Barra horizontal quando precisa, fileiras que refluem (Revisão de texto, cartão, Rotulagem, navegação da Galeria), 480 px garantidos à mensagem enquanto ela está na tela. O portão estendido achou mais que o crítico: quinze controles espremidos na Rotulagem e quatro na Galeria, e o botão «Mensagens» do rodapé com 27 de 82 px com a importação em curso (tinha um piso de um pixel, que saiu; sabotagem `aperto`), consertados. O arnês põe a linha cheia do rodapé ele mesmo (a medida não pode depender de a importação ainda correr) e prende a `QApplication` e a janela até o fim: com a máquina ocupada, quatro de dez corridas morriam em `access violation` no retorno da medida | construtor + crítico |
| 2026-09-23 | A15 | **crítico, ciclo 1: as regras de posição fechadas às brechas, e o import quebrado dito como quebrado** | O `.split()` só isenta a lista de palavras minúsculas partida por espaço; a chave de um dicionário que o módulo enumera (`list(D)`, `D.keys()`, `for x in D`, `addItems(D)`) vai para a tela e é varrida; os três casos do crítico entraram no teste anti-brecha. `test_arquitetura`: «veio Qt» sai com 3, e qualquer outra saída não zero é falha do import com o erro | construtor + crítico |
