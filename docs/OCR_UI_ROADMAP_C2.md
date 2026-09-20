# OCR/UI — roadmap do ciclo 2

> **Data:** 2026-09-20 · **Fonte:** `docs/OCR_UI_ANALISE_C2.md` (aprovada pelos críticos; §0 =
> as 20 alavancas, §8 = a ordem). Este documento detalha a **fase 1** (fiação e perdas
> silenciosas) com o formato do ciclo 1 — briefing frio, arquivos, portão, sabotagem, "Saída" —
> e lista as fases 2 e 3 por alavanca, a detalhar quando a 1 fechar. Relatório do construtor:
> `docs/quality/OCR_UI_REPORT_C2.md` (uma seção por passo, todo número com o comando ao lado).
> Não substitui `OCR_UI_ROADMAP.md` (ciclo 1), cujas pendências humanas (0b, crítico C3) continuam.

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

## 3. Fases 2 e 3 (a detalhar quando a fase 1 fechar)

- **Fase 2 — texto, glifos e janela:** B1 (leiaute em scan, alavanca 3), B2 (perfil por faixa,
  17), B3 (NAGs, 16 — usa `RepairedMove.suffix`), B5 (escore da fusão, 7), B6 (escala, 20),
  B8 (verso, T7), B9 (paralelo + cancelamento dentro da página, T8), C2 (ler a página, 10), C3
  (segunda opinião de outra família, 18), C8 (trilho/teclado, 19), C9 (pele nas abas, U6),
  C10 (coordenadas/ponto de vista das pretas, D7).
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
